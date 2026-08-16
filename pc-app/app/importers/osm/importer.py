"""OSM importer — volitelný doplněk, matching přes tag wikidata nebo A/B/C."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import REPO_ROOT, get_data_dir
from app.db.models import now_iso
from app.importers.base import CanonicalRecord
from app.importers.osm.client import OsmClient
from app.importers.osm.parser import records_from_overpass
from app.logging_setup import get_logger

SOURCE_TYPE = "osm"
SAMPLE_JSON = REPO_ROOT / "fixtures" / "import" / "osm" / "overpass.json"
_log = get_logger()


def cache_path() -> Path:
    return get_data_dir() / "cache" / "osm_last.json"


def records_from_file(path: Path, fetched_at: str | None = None) -> list[CanonicalRecord]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Neplatný OSM fixture: {path}")
    return records_from_overpass(data, fetched_at or now_iso())


def fetch_osm_records(*, use_cache: bool = False, client: OsmClient | None = None) -> list[CanonicalRecord]:
    fetched_at = now_iso()
    payload: dict[str, Any] | None = None
    if use_cache:
        path = cache_path()
        if path.is_file():
            payload = json.loads(path.read_text(encoding="utf-8"))
    if payload is None:
        client = client or OsmClient()
        payload = client.fetch_overpass()
        cache = cache_path()
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    records = records_from_overpass(payload, fetched_at)
    _log.info("osm records=%s", len(records))
    return records
