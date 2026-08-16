"""CSV otevřených dat Památkového katalogu → CanonicalRecord. Žádná síť."""

from __future__ import annotations

import csv
import io
import re
from typing import Any, Iterable

from app.importers.base import CanonicalRecord
from app.importers.http_client import decode_text
from app.services.matching import strip_diacritics

SOURCE_TYPE = "pamatkovy_katalog"
LICENSE = "CC BY 4.0"
CATALOG_BASE = "https://pamatkovykatalog.cz"

CASTLE_NAME_RE = re.compile(
    r"\b(hrad|hradu|hradem|zamek|zamku|zamkem|zamecek|zricenina|zriceniny|"
    r"tvrz|tvrze|pevnost|palac|letohradek|hradek|hradisko|hradozamek|"
    r"rozhledna|rozhledny|jeskyne)\b",
    re.IGNORECASE,
)

_TYPE_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bzricenin", re.I), "RUIN"),
    (re.compile(r"\b(hrad|hradu|hradem|hradek|hradisko)\b", re.I), "CASTLE"),
    (re.compile(r"\b(zamek|zamku|zamkem|zamecek)\b", re.I), "CHATEAU"),
    (re.compile(r"\btvrz", re.I), "MANOR"),
    (re.compile(r"\bpevnost", re.I), "FORTRESS"),
    (re.compile(r"\b(palac|letohradek)\b", re.I), "PALACE"),
    (re.compile(r"\brozhledn", re.I), "LOOKOUT_TOWER"),
    (re.compile(r"\bjeskyn", re.I), "CAVE"),
]


def cell(row: dict[str, str], *names: str) -> str | None:
    for name in names:
        if name in row and str(row[name] or "").strip():
            return str(row[name]).strip()
    lowered = {strip_diacritics(k).lower(): k for k in row}
    for name in names:
        key = lowered.get(strip_diacritics(name).lower())
        if key and str(row[key] or "").strip():
            return str(row[key]).strip()
    return None


def is_castle_like(name: str | None) -> bool:
    if not name:
        return False
    return bool(CASTLE_NAME_RE.search(strip_diacritics(name)))


def types_from_name(name: str | None) -> list[str]:
    if not name:
        return []
    text = strip_diacritics(name)
    found: list[str] = []
    for pattern, code in _TYPE_RULES:
        if pattern.search(text) and code not in found:
            found.append(code)
    return found


def heritage_from_protection(text: str | None, dataset: str) -> str | None:
    blob = strip_diacritics(f"{text or ''} {dataset}").lower()
    if "unesco" in blob or dataset == "SD":
        return None
    if "narodni" in blob or dataset == "NKP":
        return "NKP"
    if "kulturni" in blob or dataset == "KP":
        return "KP"
    return "UNKNOWN"


def _parse_csv_text(text: str) -> list[dict[str, str]]:
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    rows: list[dict[str, str]] = []
    for raw in reader:
        if not isinstance(raw, dict):
            continue
        rows.append({str(k): ("" if v is None else str(v)) for k, v in raw.items() if k})
    return rows


def parse_csv_bytes(data: bytes) -> list[dict[str, str]]:
    return _parse_csv_text(decode_text(data))


def parse_csv_path_text(text: str) -> list[dict[str, str]]:
    return _parse_csv_text(text)


def _record_from_row(row: dict[str, str], dataset: str, fetched_at: str) -> CanonicalRecord | None:
    catalog_id = cell(row, "katalogové_číslo", "katalogove_cislo")
    name = cell(row, "název", "nazev")
    if not catalog_id or not name:
        return None
    uskp = cell(row, "rejstříkové_číslo_ÚSKP", "rejstrikove_cislo_USKP")
    heritage = heritage_from_protection(cell(row, "typ_památkové_ochrany", "typ_pamatkove_ochrany"), dataset)
    unesco = 1 if dataset == "SD" or "unesco" in strip_diacritics(cell(row, "typ_památkové_ochrany") or "").lower() else None
    external_ids: dict[str, str] = {SOURCE_TYPE: catalog_id}
    if uskp:
        external_ids["uskp"] = uskp
    return CanonicalRecord(
        source_type=SOURCE_TYPE,
        external_id=catalog_id,
        external_ids=external_ids,
        name=name,
        types=types_from_name(name),
        address=cell(row, "adresa"),
        municipality=cell(row, "obec"),
        district=cell(row, "okres"),
        region=cell(row, "kraj"),
        short_description=cell(row, "anotace"),
        heritage_status=heritage,
        unesco=unesco,
        source_url=f"{CATALOG_BASE}/{catalog_id}",
        license=LICENSE,
        raw={"dataset": dataset, "row": row},
        fetched_at=fetched_at,
    )


def _merge_catalog(target: CanonicalRecord, incoming: CanonicalRecord) -> None:
    if incoming.heritage_status == "NKP":
        target.heritage_status = "NKP"
    elif incoming.heritage_status == "KP" and target.heritage_status not in {"NKP", "KP"}:
        target.heritage_status = "KP"
    if incoming.unesco:
        target.unesco = 1
    if incoming.short_description and not target.short_description:
        target.short_description = incoming.short_description
    ids = dict(target.external_ids)
    ids.update({k: v for k, v in incoming.external_ids.items() if v})
    target.external_ids = ids
    types = list(dict.fromkeys([*target.types, *incoming.types]))
    target.types = types
    alts = list(dict.fromkeys([*target.alternative_names, *incoming.alternative_names]))
    target.alternative_names = alts
    raw_sets = target.raw.get("datasets") if isinstance(target.raw.get("datasets"), list) else [target.raw]
    incoming_raw = incoming.raw.get("datasets") if isinstance(incoming.raw.get("datasets"), list) else [incoming.raw]
    target.raw = {"catalog": target.external_id, "datasets": [*raw_sets, *incoming_raw]}


def merge_catalog_records(records: Iterable[CanonicalRecord]) -> list[CanonicalRecord]:
    by_id: dict[str, CanonicalRecord] = {}
    order: list[str] = []
    for record in records:
        key = record.external_id
        if not key:
            continue
        existing = by_id.get(key)
        if existing is None:
            by_id[key] = record
            order.append(key)
            continue
        _merge_catalog(existing, record)
    return [by_id[key] for key in order]


def records_from_tables(
    tables: dict[str, list[dict[str, str]]],
    fetched_at: str,
    *,
    known_uskp: set[str] | None = None,
    known_catalog: set[str] | None = None,
    castle_only: bool = True,
) -> list[CanonicalRecord]:
    records: list[CanonicalRecord] = []
    for dataset, rows in tables.items():
        for row in rows:
            record = _record_from_row(row, dataset, fetched_at)
            if record is not None:
                records.append(record)
    merged = merge_catalog_records(records)
    if not castle_only:
        return merged
    known_uskp = known_uskp or set()
    known_catalog = known_catalog or set()
    kept: list[CanonicalRecord] = []
    for record in merged:
        uskp = record.external_ids.get("uskp")
        if (
            is_castle_like(record.name)
            or (record.external_id and record.external_id in known_catalog)
            or (uskp and uskp in known_uskp)
        ):
            kept.append(record)
    return kept


def fetch_summary(records: list[CanonicalRecord]) -> str:
    nkp = sum(1 for item in records if item.heritage_status == "NKP")
    return f"pamatkovy_katalog records={len(records)} nkp={nkp}"
