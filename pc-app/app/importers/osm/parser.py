"""OSM Overpass → CanonicalRecord. Doplněk, ne master katalog."""

from __future__ import annotations

import re
from typing import Any

from app.importers.base import CanonicalRecord

SOURCE_TYPE = "osm"
LICENSE = "ODbL"

_TYPE_FROM_CASTLE = {
    "defensive": "CASTLE",
    "stately": "CHATEAU",
    "palace": "PALACE",
    "manor": "MANOR",
    "fortified_manor": "MANOR",
    "fortress": "FORTRESS",
}


def osm_external_id(element: dict[str, Any]) -> str | None:
    kind = element.get("type")
    oid = element.get("id")
    if kind in {"node", "way", "relation"} and oid is not None:
        return f"{kind}/{oid}"
    return None


def _coords(element: dict[str, Any]) -> tuple[float | None, float | None]:
    if element.get("lat") is not None and element.get("lon") is not None:
        return float(element["lat"]), float(element["lon"])
    center = element.get("center") or {}
    if center.get("lat") is not None and center.get("lon") is not None:
        return float(center["lat"]), float(center["lon"])
    return None, None


def types_from_tags(tags: dict[str, str]) -> list[str]:
    if tags.get("tourism") == "zoo":
        return ["ZOO"]
    if tags.get("natural") == "cave_entrance":
        return ["CAVE"]
    tower_type = (tags.get("tower:type") or "").split(";")[0].strip()
    if tags.get("man_made") == "tower" and tower_type == "observation":
        return ["LOOKOUT_TOWER"]
    if tags.get("ruins") in {"yes", "true", "1"}:
        return ["RUIN"]
    castle_type = (tags.get("castle_type") or "").split(";")[0].strip()
    mapped = _TYPE_FROM_CASTLE.get(castle_type)
    if mapped:
        return [mapped]
    if tags.get("historic") == "castle":
        return ["CASTLE"]
    return []


_PRIVATE_ACCESS = frozenset({"private", "no"})
_PUBLIC_ACCESS = frozenset({"yes", "public", "permissive", "customers"})
_TOURISM_PUBLIC = frozenset({"attraction", "museum", "zoo", "yes"})
_SEASONAL_MONTH_RE = re.compile(
    r"\b(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\b",
    re.IGNORECASE,
)


def _looks_seasonal(hours: str) -> bool:
    lower = hours.casefold()
    if "off" in lower:
        return True
    return _SEASONAL_MONTH_RE.search(hours) is not None


def visitability_from_tags(tags: dict[str, str]) -> str | None:
    """Odhad z OSM tagů. Chybějící tag ≠ UNKNOWN v zápisu (vrací None)."""
    access = (tags.get("access") or "").lower()
    if access in _PRIVATE_ACCESS:
        return "PRIVATE"
    hours = str(tags.get("opening_hours") or tags.get("opening_hours:signed") or "").strip()
    if hours:
        return "SEASONAL" if _looks_seasonal(hours) else "REGULAR"
    tourism = (tags.get("tourism") or "").lower()
    if tourism in _TOURISM_PUBLIC:
        return "REGULAR"
    fee = (tags.get("fee") or "").lower()
    if fee == "yes":
        return "REGULAR"
    if fee == "no" and access in _PUBLIC_ACCESS | {""}:
        return "FREE_ACCESS"
    if access == "customers":
        return "REGULAR"
    if tags.get("ruins") in {"yes", "true", "1"}:
        return "FREE_ACCESS"
    return None


def municipality_from_tags(tags: dict[str, str]) -> str | None:
    for key in ("addr:city", "addr:municipality", "addr:town", "addr:village"):
        value = str(tags.get(key) or "").strip()
        if value:
            return value
    return None


def address_from_tags(tags: dict[str, str]) -> str | None:
    house = str(tags.get("addr:housenumber") or "").strip()
    street = str(tags.get("addr:street") or tags.get("addr:place") or "").strip()
    if street and house:
        return f"{street} {house}"
    if street:
        return street
    return None


def record_from_element(element: dict[str, Any], fetched_at: str) -> CanonicalRecord | None:
    osm_id = osm_external_id(element)
    tags = element.get("tags") if isinstance(element.get("tags"), dict) else {}
    name = str(tags.get("name:cs") or tags.get("name") or "").strip()
    if not osm_id or not name:
        return None
    lat, lon = _coords(element)
    qid = tags.get("wikidata")
    wiki = tags.get("wikipedia")
    external_ids: dict[str, str] = {SOURCE_TYPE: osm_id}
    if qid:
        external_ids["wikidata"] = qid
    if wiki:
        external_ids["wikipedia"] = wiki.replace(" ", "_")
    wikipedia_url = None
    if wiki and ":" in wiki:
        lang, title = wiki.split(":", 1)
        wikipedia_url = f"https://{lang}.wikipedia.org/wiki/{title.replace(' ', '_')}"
    website = tags.get("website") or tags.get("contact:website")
    has_hours = bool(str(tags.get("opening_hours") or tags.get("opening_hours:signed") or "").strip())
    return CanonicalRecord(
        source_type=SOURCE_TYPE,
        external_id=osm_id,
        external_ids=external_ids,
        name=name,
        types=types_from_tags(tags),
        latitude=lat,
        longitude=lon,
        address=address_from_tags(tags),
        municipality=municipality_from_tags(tags),
        official_website=website,
        wikipedia_url=wikipedia_url,
        visitability=visitability_from_tags(tags),
        opening_hours_url=website if has_hours else None,
        source_url=f"https://www.openstreetmap.org/{osm_id}",
        license=LICENSE,
        raw={"element": {"type": element.get("type"), "id": element.get("id"), "tags": tags}},
        fetched_at=fetched_at,
    )


def records_from_overpass(payload: dict[str, Any], fetched_at: str) -> list[CanonicalRecord]:
    elements = payload.get("elements") if isinstance(payload, dict) else None
    if not isinstance(elements, list):
        raise ValueError("Neplatná Overpass odpověď")
    records: list[CanonicalRecord] = []
    for element in elements:
        if not isinstance(element, dict):
            continue
        record = record_from_element(element, fetched_at)
        if record is not None:
            records.append(record)
    return records
