"""Stažení Wikidata záznamů a volitelná cache poslední SPARQL odpovědi."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import REPO_ROOT, get_data_dir
from app.db.models import now_iso
from app.importers.base import CanonicalRecord
from app.importers.wikidata.client import WikidataClient
from app.importers.wikidata.parser import count_without_gps, records_from_bundle
from app.logging_setup import get_logger
from app.services.import_progress import write_progress

SOURCE_TYPE = "wikidata"
SAMPLE_SPARQL_FIXTURE = REPO_ROOT / "fixtures" / "import" / "wikidata" / "sparql_sample.json"
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


def fetch_wikidata_records(
    *,
    use_cache: bool = False,
    client: WikidataClient | None = None,
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
    save_bundle(bundle)
    records = records_from_bundle(bundle, fetched_at)
    _log.info("wikidata fetched %s", fetch_summary(records))
    return records
