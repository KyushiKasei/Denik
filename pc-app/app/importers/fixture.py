"""Importer nad lokálním JSON fixture. Žádný SPARQL, žádná síť."""

from __future__ import annotations

import json
from pathlib import Path

from app.config import REPO_ROOT
from app.db.models import now_iso
from app.importers.base import CanonicalRecord

FIXTURE_DIR = REPO_ROOT / "fixtures" / "import"
DEFAULT_FIXTURE = FIXTURE_DIR / "small_dataset.json"
SOURCE_TYPE = "fixture"


def list_fixture_files() -> list[Path]:
    if not FIXTURE_DIR.exists():
        return []
    return sorted(FIXTURE_DIR.glob("*.json"))


def load_fixture(path: Path | None = None) -> tuple[str, list[CanonicalRecord]]:
    file_path = path or DEFAULT_FIXTURE
    data = json.loads(file_path.read_text(encoding="utf-8"))
    if isinstance(data, list):
        records_data = data
        source_type = SOURCE_TYPE
    elif isinstance(data, dict):
        records_data = data.get("records") or []
        source_type = str(data.get("source_type") or SOURCE_TYPE)
    else:
        raise ValueError(f"Neplatný fixture soubor: {file_path}")
    fetched = now_iso()
    records: list[CanonicalRecord] = []
    for item in records_data:
        if not isinstance(item, dict):
            continue
        payload = dict(item)
        payload.setdefault("source_type", source_type)
        payload.setdefault("fetched_at", fetched)
        payload.setdefault("raw", item)
        records.append(CanonicalRecord.from_dict(payload))
    return source_type, records
