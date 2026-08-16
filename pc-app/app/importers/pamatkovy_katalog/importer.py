"""Památkový katalog — CSV otevřená data, matching přes ÚSKP / katalogové číslo."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import REPO_ROOT, get_data_dir
from app.db.models import now_iso
from app.importers.base import CanonicalRecord
from app.importers.pamatkovy_katalog.client import KatalogClient
from app.importers.pamatkovy_katalog.parser import fetch_summary, parse_csv_path_text, records_from_tables
from app.logging_setup import get_logger
from app.services.import_progress import write_progress

SOURCE_TYPE = "pamatkovy_katalog"
SAMPLE_CSV = REPO_ROOT / "fixtures" / "import" / "pamatkovy_katalog" / "sample.csv"
_log = get_logger()


def cache_path() -> Path:
    return get_data_dir() / "cache" / "pamatkovy_katalog_last.json"


def save_tables(tables: dict[str, list[dict[str, str]]]) -> Path:
    path = cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tables, ensure_ascii=False), encoding="utf-8")
    return path


def load_tables_file(path: Path) -> dict[str, list[dict[str, str]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Neplatný cache Památkového katalogu: {path}")
    return {str(k): list(v) for k, v in data.items() if isinstance(v, list)}


def records_from_csv_file(
    path: Path,
    fetched_at: str | None = None,
    *,
    dataset: str = "NKP",
    known_uskp: set[str] | None = None,
    known_catalog: set[str] | None = None,
) -> list[CanonicalRecord]:
    text = path.read_text(encoding="utf-8")
    rows = parse_csv_path_text(text)
    return records_from_tables(
        {dataset: rows},
        fetched_at or now_iso(),
        known_uskp=known_uskp,
        known_catalog=known_catalog,
    )


def records_from_cached_tables(
    tables: dict[str, list[dict[str, str]]],
    fetched_at: str | None = None,
    *,
    known_uskp: set[str] | None = None,
    known_catalog: set[str] | None = None,
) -> list[CanonicalRecord]:
    return records_from_tables(
        tables,
        fetched_at or now_iso(),
        known_uskp=known_uskp,
        known_catalog=known_catalog,
    )


def fetch_pamatkovy_katalog_records(
    *,
    use_cache: bool = False,
    client: KatalogClient | None = None,
    known_uskp: set[str] | None = None,
    known_catalog: set[str] | None = None,
) -> list[CanonicalRecord]:
    fetched_at = now_iso()
    tables: dict[str, list[dict[str, str]]] | None = None
    if use_cache:
        path = cache_path()
        if path.is_file():
            tables = load_tables_file(path)
            _log.info("pamatkovy_katalog loaded from cache")
    if tables is None:
        client = client or KatalogClient()

        def _on_dataset(code: str, index: int, total: int) -> None:
            write_progress(
                status="running",
                phase="fetch",
                source_type=SOURCE_TYPE,
                current=index,
                total=total,
                message=f"Stahuji CSV {code} ({index} / {total})",
                force=True,
            )

        tables = client.fetch_tables(on_dataset=_on_dataset)
        save_tables(tables)
    records = records_from_cached_tables(
        tables,
        fetched_at,
        known_uskp=known_uskp,
        known_catalog=known_catalog,
    )
    _log.info("pamatkovy_katalog %s", fetch_summary(records))
    return records
