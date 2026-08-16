"""Homepage oficiálního webu → visitability. Nestahuje se hrady.cz ani celé katalogy."""

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
from app.importers.official_web.parser import (
    SOURCE_TYPE,
    classify_html,
    record_from_place,
    skip_website,
    website_host,
)
from app.logging_setup import get_logger
from app.services.import_progress import write_progress
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


def _is_ruin(place: Place) -> bool:
    if place.condition == "RUIN":
        return True
    return any(item.code == "RUIN" for item in place.types)


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


def records_for_places(
    places: list[Place],
    *,
    fetch_html: FetchFn,
    fetched_at: str | None = None,
    on_progress: ProgressFn | None = None,
) -> list[CanonicalRecord]:
    when = fetched_at or now_iso()
    candidates = [
        place
        for place in places
        if not place.archived_at
        and place.visitability == "UNKNOWN"
        and not _is_ruin(place)
        and not _has_visitability_override(place)
        and is_http_url(place.official_website)
        and not skip_website(place.official_website)
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
) -> list[CanonicalRecord]:
    path = cache_path()
    if use_cache and path.is_file():
        records = records_from_file(path)
        _log.info("official_web loaded from cache records=%s", len(records))
        return records

    places = list(session.scalars(select(Place).where(Place.archived_at.is_(None))).all())

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

    records = records_for_places(places, fetch_html=_fetch, on_progress=_on_progress)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"records": [item.to_dict() for item in records]}, ensure_ascii=False),
        encoding="utf-8",
    )
    _log.info("official_web classified=%s of unknown-with-website", len(records))
    return records
