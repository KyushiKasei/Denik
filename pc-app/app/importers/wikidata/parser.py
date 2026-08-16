"""SPARQL JSON → CanonicalRecord. Žádná síť."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import quote, unquote, urlparse

from app.importers.base import CanonicalRecord

SOURCE_TYPE = "wikidata"
LICENSE = "CC0"

_WKT_POINT_RE = re.compile(
    r"Point\s*\(\s*([+-]?\d+(?:\.\d+)?)\s+([+-]?\d+(?:\.\d+)?)\s*\)",
    re.IGNORECASE,
)
_QID_RE = re.compile(r"^Q\d+$")


def binding_value(binding: dict[str, Any], key: str) -> str | None:
    cell = binding.get(key)
    if not isinstance(cell, dict):
        return None
    value = cell.get("value")
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def qid_from_uri(uri: str | None) -> str | None:
    if not uri:
        return None
    part = uri.rstrip("/").split("/")[-1]
    return part if _QID_RE.match(part) else None


def parse_wkt_point(value: str | None) -> tuple[float | None, float | None]:
    """WKT Point(lon lat) → (latitude, longitude)."""
    if not value:
        return None, None
    match = _WKT_POINT_RE.search(value)
    if not match:
        return None, None
    lon = float(match.group(1))
    lat = float(match.group(2))
    if not (-90.0 <= lat <= 90.0 and -180.0 <= lon <= 180.0):
        return None, None
    return lat, lon


def compose_address(
    house_number: str | None,
    settlement: str | None,
    municipality: str | None,
) -> str | None:
    """Č.p. (P4856) + část obce (přímé P131), ne prostý text Wikipedie."""
    house = (house_number or "").strip() or None
    settlement_name = (settlement or "").strip() or None
    municipality_name = (municipality or "").strip() or None
    if settlement_name and municipality_name and settlement_name.casefold() == municipality_name.casefold():
        place_part = municipality_name
    else:
        place_part = settlement_name or municipality_name
    if house and place_part:
        return f"{place_part} {house}"
    if settlement_name and settlement_name != municipality_name:
        return settlement_name
    return None


def clean_district(name: str | None) -> str | None:
    if not name:
        return None
    text = name.strip()
    lowered = text.casefold()
    if lowered.startswith("okres "):
        text = text[6:].strip()
    return text or None


def wikipedia_external_id(url: str) -> str | None:
    parsed = urlparse(url)
    host = parsed.netloc.lower()
    if not host.endswith("wikipedia.org"):
        return None
    lang = host.split(".")[0]
    if "/wiki/" not in parsed.path:
        return None
    title = unquote(parsed.path.split("/wiki/", 1)[1])
    if not title:
        return None
    return f"{lang}:{title}"


def image_from_p18(url: str | None) -> dict[str, str] | None:
    """URL z P18 (Special:FilePath) → odkazy na Commons. Metadata licence až fáze 5."""
    if not url:
        return None
    filename = None
    marker = "Special:FilePath/"
    if marker in url:
        filename = unquote(url.split(marker, 1)[1].split("?")[0])
    elif "/wiki/File:" in url:
        filename = unquote(url.split("/wiki/File:", 1)[1].split("?")[0])
    if not filename:
        return None
    filename = filename.replace(" ", "_")
    quoted = quote(filename, safe="._-()")
    file_page = f"https://commons.wikimedia.org/wiki/File:{quoted}"
    path_url = f"https://commons.wikimedia.org/wiki/Special:FilePath/{quoted}"
    return {
        "source": "wikimedia_commons",
        "original_url": file_page,
        "thumbnail_url": f"{path_url}?width=640",
        "source_url": file_page,
    }


def count_without_gps(records: list[CanonicalRecord]) -> int:
    return sum(1 for item in records if item.latitude is None or item.longitude is None)


def _empty(value: Any) -> bool:
    return value is None or value == "" or value == []


def merge_records(records: list[CanonicalRecord]) -> list[CanonicalRecord]:
    """Sloučí duplicitní SPARQL řádky a stejné QID z více typových dotazů."""
    by_qid: dict[str, CanonicalRecord] = {}
    order: list[str] = []
    for record in records:
        qid = record.external_id
        if not qid:
            continue
        existing = by_qid.get(qid)
        if existing is None:
            by_qid[qid] = record
            order.append(qid)
            continue
        _merge_into(existing, record)
    return [by_qid[qid] for qid in order]


def _merge_into(target: CanonicalRecord, incoming: CanonicalRecord) -> None:
    types = list(dict.fromkeys([*target.types, *incoming.types]))
    target.types = types
    alts = list(dict.fromkeys([*target.alternative_names, *incoming.alternative_names]))
    target.alternative_names = alts
    ids = dict(target.external_ids)
    ids.update({k: v for k, v in incoming.external_ids.items() if v})
    target.external_ids = ids
    for field_name in (
        "name",
        "latitude",
        "longitude",
        "address",
        "municipality",
        "district",
        "region",
        "official_website",
        "wikipedia_url",
        "source_url",
        "license",
        "fetched_at",
        "visitability",
    ):
        if _empty(getattr(target, field_name)) and not _empty(getattr(incoming, field_name)):
            setattr(target, field_name, getattr(incoming, field_name))
    if target.image is None and incoming.image is not None:
        target.image = incoming.image
    raw_rows = []
    if isinstance(target.raw.get("bindings"), list):
        raw_rows.extend(target.raw["bindings"])
    elif target.raw:
        raw_rows.append(target.raw)
    if isinstance(incoming.raw.get("bindings"), list):
        raw_rows.extend(incoming.raw["bindings"])
    elif incoming.raw:
        raw_rows.append(incoming.raw)
    target.raw = {"qid": target.external_id, "bindings": raw_rows}


def parse_sparql_response(
    data: dict[str, Any],
    *,
    extra_type: str | None = None,
    fetched_at: str,
) -> list[CanonicalRecord]:
    results = data.get("results") if isinstance(data, dict) else None
    bindings = results.get("bindings") if isinstance(results, dict) else None
    if not isinstance(bindings, list):
        raise ValueError("Neplatná SPARQL JSON odpověď: chybí results.bindings")
    records: list[CanonicalRecord] = []
    for binding in bindings:
        if not isinstance(binding, dict):
            continue
        record = _record_from_binding(binding, extra_type=extra_type, fetched_at=fetched_at)
        if record is not None:
            records.append(record)
    return merge_records(records)


def records_from_bundle(bundle: dict[str, Any], fetched_at: str) -> list[CanonicalRecord]:
    """Bundle {TYPE_CODE: sparql_json} nebo holá SPARQL odpověď."""
    if "results" in bundle and "head" in bundle:
        extra = bundle.get("extra_type")
        extra_type = str(extra) if extra else None
        return parse_sparql_response(bundle, extra_type=extra_type, fetched_at=fetched_at)
    records: list[CanonicalRecord] = []
    for type_code, payload in bundle.items():
        if not isinstance(payload, dict) or "results" not in payload:
            continue
        records.extend(
            parse_sparql_response(payload, extra_type=str(type_code), fetched_at=fetched_at)
        )
    return merge_records(records)


def _record_from_binding(
    binding: dict[str, Any],
    *,
    extra_type: str | None,
    fetched_at: str,
) -> CanonicalRecord | None:
    qid = qid_from_uri(binding_value(binding, "item"))
    name = binding_value(binding, "itemLabel")
    if not qid or not name:
        return None
    lat, lon = parse_wkt_point(binding_value(binding, "coord"))
    website = binding_value(binding, "web")
    wikipedia = binding_value(binding, "article")
    uskp = binding_value(binding, "uskp")
    municipality = binding_value(binding, "obecLabel")
    settlement = binding_value(binding, "castLabel")
    address = compose_address(binding_value(binding, "cp"), settlement, municipality)
    types: list[str] = []
    if extra_type:
        types.append(extra_type)
    external_ids: dict[str, str] = {SOURCE_TYPE: qid}
    if uskp:
        external_ids["uskp"] = uskp
    if wikipedia:
        wiki_id = wikipedia_external_id(wikipedia)
        if wiki_id:
            external_ids["wikipedia"] = wiki_id
    return CanonicalRecord(
        source_type=SOURCE_TYPE,
        external_id=qid,
        external_ids=external_ids,
        name=name,
        types=types,
        latitude=lat,
        longitude=lon,
        address=address,
        municipality=municipality,
        district=clean_district(binding_value(binding, "okresLabel")),
        region=binding_value(binding, "krajLabel"),
        official_website=website,
        wikipedia_url=wikipedia,
        visitability="FREE_ACCESS" if extra_type == "RUIN" else None,
        source_url=f"https://www.wikidata.org/wiki/{qid}",
        license=LICENSE,
        image=image_from_p18(binding_value(binding, "image")),
        raw={"binding": binding, "extra_type": extra_type},
        fetched_at=fetched_at,
    )
