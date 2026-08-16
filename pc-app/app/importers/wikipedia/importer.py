"""Wikipedia importer: URL + QID, bez textu článků."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import REPO_ROOT, get_data_dir
from app.db.models import now_iso
from app.importers.base import CanonicalRecord
from app.importers.wikipedia.client import WikipediaClient
from app.importers.wikipedia.parser import merge_wikipedia_records, records_from_category_payload
from app.logging_setup import get_logger

SOURCE_TYPE = "wikipedia"
SAMPLE_JSON = REPO_ROOT / "fixtures" / "import" / "wikipedia" / "categorymembers.json"
_log = get_logger()


def cache_path() -> Path:
    return get_data_dir() / "cache" / "wikipedia_last.json"


def records_from_file(path: Path, fetched_at: str | None = None) -> list[CanonicalRecord]:
    data = json.loads(path.read_text(encoding="utf-8"))
    when = fetched_at or now_iso()
    if isinstance(data, dict) and "categories" in data:
        records: list[CanonicalRecord] = []
        for item in data["categories"]:
            if isinstance(item, dict):
                records.extend(records_from_category_payload(item, when))
        return merge_wikipedia_records(records)
    if isinstance(data, dict):
        return merge_wikipedia_records(records_from_category_payload(data, when))
    raise ValueError(f"Neplatný Wikipedia fixture: {path}")


def fetch_wikipedia_records(*, use_cache: bool = False, client: WikipediaClient | None = None) -> list[CanonicalRecord]:
    fetched_at = now_iso()
    bundle: dict[str, Any] | None = None
    if use_cache:
        path = cache_path()
        if path.is_file():
            bundle = json.loads(path.read_text(encoding="utf-8"))
    if bundle is None:
        client = client or WikipediaClient()
        bundle = client.fetch_bundle()
        cache = cache_path()
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(bundle, ensure_ascii=False), encoding="utf-8")
    records: list[CanonicalRecord] = []
    for payload in bundle.values():
        if isinstance(payload, dict):
            records.extend(records_from_category_payload(payload, fetched_at))
    merged = merge_wikipedia_records(records)
    _log.info("wikipedia records=%s", len(merged))
    return merged
