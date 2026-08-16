"""Číselník obcí / okresů / krajů RÚIAN. Neplný import adres."""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass

from app.importers.base import CanonicalRecord
from app.importers.http_client import decode_text
from app.services.matching import normalize_label

SOURCE_TYPE = "ruian"
LICENSE = "CC BY 4.0"


@dataclass(frozen=True)
class RuianObec:
    obec_kod: str
    obec_nazev: str
    okres_kod: str
    okres_nazev: str
    kraj_kod: str
    kraj_nazev: str


def _rows_from_csv(text: str) -> list[dict[str, str]]:
    sample = text[:2048]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=";,")
    except csv.Error:
        dialect = csv.get_dialect("excel")
        dialect.delimiter = ";"
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    out: list[dict[str, str]] = []
    for raw in reader:
        if not isinstance(raw, dict):
            continue
        out.append({str(k).strip(): ("" if v is None else str(v).strip()) for k, v in raw.items() if k})
    return out


def parse_codebook_bytes(data: bytes) -> list[dict[str, str]]:
    return _rows_from_csv(decode_text(data))


def parse_codebook_text(text: str) -> list[dict[str, str]]:
    return _rows_from_csv(text)


def _valid_row(row: dict[str, str]) -> bool:
    until = (row.get("PLATI_DO") or row.get("plati_do") or "").strip()
    return not until


def build_lookup(
    obce: list[dict[str, str]],
    okresy: list[dict[str, str]],
    kraje: list[dict[str, str]],
) -> list[RuianObec]:
    okres_by_kod: dict[str, dict[str, str]] = {}
    for row in okresy:
        if not _valid_row(row):
            continue
        kod = row.get("KOD") or row.get("kod")
        if kod:
            okres_by_kod[kod] = row
    kraj_by_kod: dict[str, dict[str, str]] = {}
    for row in kraje:
        if not _valid_row(row):
            continue
        kod = row.get("KOD") or row.get("kod")
        if kod:
            kraj_by_kod[kod] = row
    result: list[RuianObec] = []
    for row in obce:
        if not _valid_row(row):
            continue
        kod = row.get("KOD") or row.get("kod")
        nazev = row.get("NAZEV") or row.get("nazev")
        okres_kod = row.get("OKRES_KOD") or row.get("okres_kod") or ""
        if not kod or not nazev:
            continue
        okres = okres_by_kod.get(okres_kod, {})
        kraj_kod = okres.get("VUSC_KOD") or okres.get("vusc_kod") or ""
        kraj = kraj_by_kod.get(kraj_kod, {})
        result.append(
            RuianObec(
                obec_kod=kod,
                obec_nazev=nazev,
                okres_kod=okres_kod,
                okres_nazev=okres.get("NAZEV") or okres.get("nazev") or "",
                kraj_kod=kraj_kod,
                kraj_nazev=kraj.get("NAZEV") or kraj.get("nazev") or "",
            )
        )
    return result


class RuianLookup:
    def __init__(self, items: list[RuianObec]) -> None:
        self.items = items
        self._by_name: dict[str, list[RuianObec]] = {}
        for item in items:
            self._by_name.setdefault(normalize_label(item.obec_nazev), []).append(item)

    def match(
        self,
        municipality: str | None,
        district: str | None = None,
        region: str | None = None,
    ) -> RuianObec | None:
        if not municipality:
            return None
        candidates = self._by_name.get(normalize_label(municipality), [])
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0]
        if district:
            dist = normalize_label(district)
            if dist.startswith("okres "):
                dist = dist[6:].strip()
            narrowed = [item for item in candidates if normalize_label(item.okres_nazev) == dist]
            if len(narrowed) == 1:
                return narrowed[0]
            candidates = narrowed or candidates
        if region and len(candidates) > 1:
            reg = normalize_label(region)
            by_region = [item for item in candidates if normalize_label(item.kraj_nazev) == reg]
            if len(by_region) == 1:
                return by_region[0]
        if len(candidates) == 1:
            return candidates[0]
        return None


def match_obec(
    lookup: list[RuianObec],
    municipality: str | None,
    district: str | None = None,
    region: str | None = None,
) -> RuianObec | None:
    return RuianLookup(lookup).match(municipality, district, region)


def record_for_place(
    *,
    name: str,
    external_ids: dict[str, str],
    hit: RuianObec | None,
    fetched_at: str,
    latitude: float | None = None,
    longitude: float | None = None,
    types: list[str] | None = None,
    address: str | None = None,
    municipality: str | None = None,
    district: str | None = None,
    region: str | None = None,
    raw_extra: dict[str, str] | None = None,
) -> CanonicalRecord:
    raw = dict(raw_extra or {})
    if hit is not None:
        municipality = hit.obec_nazev
        district = hit.okres_nazev
        region = hit.kraj_nazev
        raw.update(
            {
                "obec_kod": hit.obec_kod,
                "okres_kod": hit.okres_kod,
                "kraj_kod": hit.kraj_kod,
            }
        )
    return CanonicalRecord(
        source_type=SOURCE_TYPE,
        external_id=None,
        external_ids=dict(external_ids),
        name=name,
        types=list(types or []),
        latitude=latitude,
        longitude=longitude,
        address=address,
        municipality=municipality,
        municipality_code=hit.obec_kod if hit else None,
        district=district,
        district_code=hit.okres_kod if hit else None,
        region=region,
        region_code=hit.kraj_kod if hit else None,
        license=LICENSE,
        source_url="https://www.cuzk.gov.cz/ruian",
        raw=raw,
        fetched_at=fetched_at,
        allow_create=False,
    )
