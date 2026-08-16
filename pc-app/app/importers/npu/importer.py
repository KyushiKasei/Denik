"""Importer spravovaných objektů NPÚ: URL a návštěvní odkazy."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import REPO_ROOT, get_data_dir
from app.db.models import now_iso
from app.importers.base import CanonicalRecord
from app.importers.npu.client import NpuClient
from app.importers.npu.parser import records_from_managed_list, records_from_sparql
from app.logging_setup import get_logger

SOURCE_TYPE = "npu"
SAMPLE_JSON = REPO_ROOT / "fixtures" / "import" / "npu" / "managed.json"
_log = get_logger()


def cache_path() -> Path:
    return get_data_dir() / "cache" / "npu_last.json"


def records_from_file(path: Path, fetched_at: str | None = None) -> list[CanonicalRecord]:
    data = json.loads(path.read_text(encoding="utf-8"))
    items = data.get("records") if isinstance(data, dict) else data
    if not isinstance(items, list):
        raise ValueError(f"Neplatný NPÚ fixture: {path}")
    return records_from_managed_list([item for item in items if isinstance(item, dict)], fetched_at or now_iso())


def fetch_npu_records(*, use_cache: bool = False, client: NpuClient | None = None) -> list[CanonicalRecord]:
    fetched_at = now_iso()
    payload: dict[str, Any] | None = None
    if use_cache:
        path = cache_path()
        if path.is_file():
            payload = json.loads(path.read_text(encoding="utf-8"))
            _log.info("npu loaded from cache")
    if payload is None:
        client = client or NpuClient()
        payload = client.fetch_sparql()
        cache = cache_path()
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    records = records_from_sparql(payload, fetched_at)
    _log.info("npu records=%s", len(records))
    return records
