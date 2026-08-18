"""Homepage oficiálního webu → visitability a návštěvní URL. Nestahuje se hrady.cz ani celé katalogy."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_data_dir
from app.db.models import Place, now_iso
from app.importers.base import CanonicalRecord
from app.importers.http_client import DownloadError, fetch_bytes
from app.importers.npu.parser import visitor_urls
from app.importers.official_web.parser import (
    SOURCE_TYPE,
    WebsiteHint,
    classify_html,
    record_from_place,
    skip_website,
    website_host,
)
from app.logging_setup import get_logger
from app.services.import_progress import write_progress
from app.services.ruins import is_ruin
from app.services.source_urls import is_http_url

_log = get_logger()
MIN_INTERVAL_S = 1.1
MAX_HTML_BYTES = 500_000
FetchFn = Callable[[str], str | None]
ProgressFn = Callable[[int, int, str], None]


def cache_path() -> Path:
    return get_data_dir() / "cache" / "official_web_last.json"


def records_from_file(path: Path, fetched_at: str | None = None) -> list[CanonicalRecord]:
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("records") if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ValueError(f"Neplatný official_web fixture: {path}")
    when = fetched_at or now_iso()
    records: list[CanonicalRecord] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        record = CanonicalRecord.from_dict({**item, "fetched_at": item.get("fetched_at") or when})
        record.source_type = SOURCE_TYPE
        record.allow_create = False
        records.append(record)
    return records


def _place_external_ids(place: Place) -> dict[str, str]:
    return {
        source.source_type: source.external_id
        for source in place.sources
        if source.external_id and source.source_type != SOURCE_TYPE
    }


def _has_visitability_override(place: Place) -> bool:
    return any(item.field_name == "visitability" for item in place.field_overrides)


def can_enrich_place(place: Place) -> bool:
    if place.archived_at or _is_ruin(place) or _has_visitability_override(place):
        return False
    return is_http_url(place.official_website) and not skip_website(place.official_website)


def _is_ruin(place: Place) -> bool:
    return is_ruin(place)


def _decode_html(raw: bytes) -> str:
    snippet = raw[:MAX_HTML_BYTES]
    for encoding in ("utf-8", "cp1250", "latin-1"):
        try:
            return snippet.decode(encoding)
        except UnicodeDecodeError:
            continue
    return snippet.decode("utf-8", errors="replace")


def _looks_like_html(text: str) -> bool:
    lowered = text[:2000].casefold()
    return "<html" in lowered or "<body" in lowered or "<a " in lowered or "<nav" in lowered


def fetch_homepage(url: str, *, transport: Any = None, timeout: float = 20.0) -> str | None:
    try:
        raw = fetch_bytes(url, timeout=timeout, transport=transport, accept="text/html")
    except DownloadError:
        return None
    text = _decode_html(raw)
    if not _looks_like_html(text):
        return None
    return text


def _with_npu_urls(website: str, hint: WebsiteHint, check_url: FetchFn | None) -> WebsiteHint:
    if check_url is None:
        return hint
    hours, tickets = visitor_urls(website)
    hours_url = hint.opening_hours_url
    ticket_url = hint.ticket_url
    if not hours_url and hours and not skip_website(hours) and check_url(hours):
        hours_url = hours
    if not ticket_url and tickets and not skip_website(tickets) and check_url(tickets):
        ticket_url = tickets
    if hours_url == hint.opening_hours_url and ticket_url == hint.ticket_url:
        return hint
    visitability = hint.visitability
    if visitability is None and (hours_url or ticket_url):
        visitability = "REGULAR"
    return WebsiteHint(visitability, hours_url, ticket_url)


def _needs_web_enrichment(place: Place, *, selected: bool) -> bool:
    if selected:
        return True
    if (place.visitability or "UNKNOWN") == "UNKNOWN":
        return True
    if not (place.opening_hours_url or "").strip():
        return True
    if not (place.ticket_url or "").strip():
        return True
    return False


def records_for_places(
    places: list[Place],
    *,
    fetch_html: FetchFn,
    fetched_at: str | None = None,
    on_progress: ProgressFn | None = None,
    selected: bool = False,
    check_url: FetchFn | None = None,
) -> list[CanonicalRecord]:
    when = fetched_at or now_iso()
    candidates = [
        place
        for place in places
        if not place.archived_at
        and not _is_ruin(place)
        and not _has_visitability_override(place)
        and is_http_url(place.official_website)
        and not skip_website(place.official_website)
        and _needs_web_enrichment(place, selected=selected)
    ]
    records: list[CanonicalRecord] = []
    total = len(candidates)
    for index, place in enumerate(candidates, start=1):
        website = str(place.official_website)
        host = website_host(website)
        if on_progress:
            on_progress(index, total, place.name)
        if not host:
            continue
        html = fetch_html(website)
        if not html:
            continue
        hint = classify_html(html, base_url=website)
        hint = _with_npu_urls(website, hint, check_url)
        record = record_from_place(
            name=place.name,
            website=website,
            host=host,
            hint=hint,
            external_ids=_place_external_ids(place),
            fetched_at=when,
        )
        if record is not None:
            records.append(record)
    return records


def fetch_official_web_records(
    session: Session,
    *,
    use_cache: bool = False,
    fetch_html: FetchFn | None = None,
    sleep: Any = time.sleep,
    public_ids: list[str] | None = None,
) -> list[CanonicalRecord]:
    path = cache_path()
    selected_ids = [item for item in (public_ids or []) if item]
    if use_cache and path.is_file():
        records = records_from_file(path)
        _log.info("official_web loaded from cache records=%s", len(records))
        return records

    query = select(Place).where(Place.archived_at.is_(None))
    places = list(session.scalars(query).all())
    if selected_ids:
        wanted = {item.casefold() for item in selected_ids}
        places = [place for place in places if place.public_id.casefold() in wanted]

    def _on_progress(current: int, total: int, name: str) -> None:
        write_progress(
            phase="fetch",
            current=current,
            total=total,
            current_name=name,
            message=f"Oficiální web {current} / {total}",
        )

    last_request = 0.0

    def _fetch(url: str) -> str | None:
        nonlocal last_request
        if fetch_html is not None:
            return fetch_html(url)
        wait = MIN_INTERVAL_S - (time.monotonic() - last_request)
        if wait > 0 and sleep is not None:
            sleep(wait)
        html = fetch_homepage(url)
        last_request = time.monotonic()
        return html

    records = records_for_places(
        places,
        fetch_html=_fetch,
        on_progress=_on_progress,
        selected=bool(selected_ids),
        check_url=_fetch,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"records": [item.to_dict() for item in records]}, ensure_ascii=False),
        encoding="utf-8",
    )
    _log.info("official_web classified=%s selected=%s", len(records), bool(selected_ids))
    return records
