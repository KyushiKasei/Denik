"""Stažení Wikidata záznamů a volitelná cache poslední SPARQL odpovědi."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.config import REPO_ROOT, get_data_dir
from app.db.models import Place, PlacePhoto, PlaceSource, now_iso
from app.importers.base import CanonicalRecord
from app.importers.wikidata.client import WikidataClient
from app.importers.wikidata.parser import (
    apply_condition_bindings,
    apply_style_bindings,
    count_without_gps,
    qids_in_bundle,
    records_from_bundle,
)
from app.importers.wikidata.query import CONDITION_KEY, EXISTING_QIDS_KEY, STYLE_KEY
from app.logging_setup import get_logger
from app.services.import_progress import write_progress

SOURCE_TYPE = "wikidata"
SAMPLE_SPARQL_FIXTURE = REPO_ROOT / "fixtures" / "import" / "wikidata" / "sparql_sample.json"
_QID_RE = re.compile(r"^Q\d+$")
_log = get_logger()


def cache_path() -> Path:
    return get_data_dir() / "cache" / "wikidata_last.json"


def save_bundle(bundle: dict[str, Any]) -> Path:
    path = cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
    return path


def load_bundle_file(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Neplatný Wikidata fixture: {path}")
    return data


def records_from_file(path: Path, fetched_at: str | None = None) -> list[CanonicalRecord]:
    return records_from_bundle(load_bundle_file(path), fetched_at or now_iso())


def fetch_summary(records: list[CanonicalRecord]) -> str:
    no_gps = count_without_gps(records)
    type_counts: dict[str, int] = {}
    for record in records:
        for code in record.types or ["?"]:
            type_counts[code] = type_counts.get(code, 0) + 1
    types = ", ".join(f"{code}={n}" for code, n in type_counts.items())
    return f"Wikidata records={len(records)} without_gps={no_gps} types=[{types}]"


def qids_needing_p18(session: Session, known_qids: set[str]) -> list[str]:
    """QID v katalogu bez fotky, která typový SPARQL nevrátil."""
    has_photo = exists(select(PlacePhoto.id).where(PlacePhoto.place_id == Place.id))
    rows = session.scalars(
        select(PlaceSource.external_id)
        .join(Place, Place.id == PlaceSource.place_id)
        .where(
            PlaceSource.source_type == SOURCE_TYPE,
            Place.archived_at.is_(None),
            PlaceSource.external_id.is_not(None),
            ~has_photo,
        )
    ).all()
    found: set[str] = set()
    for qid in rows:
        if not qid or qid in known_qids or not _QID_RE.match(qid):
            continue
        found.add(qid)
    return sorted(found)


def qids_needing_condition(session: Session, known_qids: set[str]) -> list[str]:
    rows = session.scalars(
        select(PlaceSource.external_id)
        .join(Place, Place.id == PlaceSource.place_id)
        .where(
            PlaceSource.source_type == SOURCE_TYPE,
            Place.archived_at.is_(None),
            PlaceSource.external_id.is_not(None),
            Place.condition.in_(("UNKNOWN", "")),
        )
    ).all()
    found: set[str] = set(known_qids)
    for qid in rows:
        if qid and _QID_RE.match(qid):
            found.add(qid)
    return sorted(found)


def fetch_wikidata_records(
    *,
    use_cache: bool = False,
    client: WikidataClient | None = None,
    session: Session | None = None,
) -> list[CanonicalRecord]:
    fetched_at = now_iso()
    if use_cache:
        path = cache_path()
        if path.is_file():
            records = records_from_file(path, fetched_at)
            _log.info("wikidata loaded from cache %s", fetch_summary(records))
            return records
        _log.info("wikidata cache missing, fetching SPARQL")
    client = client or WikidataClient()

    def _on_type(type_code: str, index: int, total: int) -> None:
        write_progress(
            status="running",
            phase="fetch",
            source_type=SOURCE_TYPE,
            current=index,
            total=total,
            message=f"SPARQL {type_code} ({index} / {total})",
            force=True,
        )

    bundle = client.fetch_bundle(on_type=_on_type)
    if session is not None:
        missing = qids_needing_p18(session, qids_in_bundle(bundle))
        if missing:

            def _on_batch(index: int, total: int, size: int) -> None:
                write_progress(
                    status="running",
                    phase="fetch",
                    source_type=SOURCE_TYPE,
                    current=index,
                    total=total,
                    message=f"SPARQL P18 existujících QID ({index} / {total}, {size})",
                    force=True,
                )

            bundle[EXISTING_QIDS_KEY] = client.fetch_items(missing, on_batch=_on_batch)
    records = records_from_bundle(bundle, fetched_at)
    condition_qids = sorted(
        {
            record.external_id
            for record in records
            if record.external_id and _QID_RE.match(record.external_id)
        }
    )
    if session is not None:
        condition_qids = qids_needing_condition(session, set(condition_qids))
    if condition_qids:

        def _on_condition(index: int, total: int, size: int) -> None:
            write_progress(
                status="running",
                phase="fetch",
                source_type=SOURCE_TYPE,
                current=index,
                total=total,
                message=f"SPARQL stav objektu ({index} / {total}, {size})",
                force=True,
            )

        bundle[CONDITION_KEY] = client.fetch_conditions(condition_qids, on_batch=_on_condition)
        apply_condition_bindings(records, bundle[CONDITION_KEY])
    style_qids = sorted(
        {
            record.external_id
            for record in records
            if record.external_id and _QID_RE.match(record.external_id)
        }
    )
    if style_qids:

        def _on_style(index: int, total: int, size: int) -> None:
            write_progress(
                status="running",
                phase="fetch",
                source_type=SOURCE_TYPE,
                current=index,
                total=total,
                message=f"SPARQL sloh a rok ({index} / {total}, {size})",
                force=True,
            )

        bundle[STYLE_KEY] = client.fetch_styles(style_qids, on_batch=_on_style)
        apply_style_bindings(records, bundle[STYLE_KEY])
    save_bundle(bundle)
    _log.info("wikidata fetched %s", fetch_summary(records))
    return records
