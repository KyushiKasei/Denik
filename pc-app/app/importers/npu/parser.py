"""Objekty ve správě NPÚ — strukturovaná fakta a URL, ne autorské texty."""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from app.importers.base import CanonicalRecord
from app.importers.wikidata.parser import qid_from_uri

SOURCE_TYPE = "npu"
LICENSE = "URL only; NPÚ website texts/photos are not imported"
NPU_QID = "Q12039181"

_TYPE_MAP = {
    "hrad": "CASTLE",
    "zamek": "CHATEAU",
    "zámek": "CHATEAU",
    "zricenina": "RUIN",
    "zřícenina": "RUIN",
    "tvrz": "MANOR",
    "rozhledna": "LOOKOUT_TOWER",
    "jeskyne": "CAVE",
    "jeskyně": "CAVE",
}


def npu_slug(website: str | None) -> str | None:
    if not website:
        return None
    host = urlparse(website).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host or None


def visitor_urls(website: str | None) -> tuple[str | None, str | None]:
    """Konvenční návštěvní odkazy NPÚ webů objektů. Nestahuje se HTML."""
    if not website:
        return None, None
    parsed = urlparse(website)
    host = parsed.netloc.lower()
    if not parsed.scheme or not host:
        return None, None
    if host.rstrip("/") in {"npu.cz", "www.npu.cz"}:
        return None, None
    origin = f"{parsed.scheme}://{parsed.netloc}"
    return (
        f"{origin}/cs/informace-pro-navstevniky/navstevni-doba",
        f"{origin}/cs/informace-pro-navstevniky/vstupne",
    )


def types_from_labels(labels: list[str]) -> list[str]:
    found: list[str] = []
    for label in labels:
        key = label.strip().casefold()
        code = _TYPE_MAP.get(key)
        if code and code not in found:
            found.append(code)
    return found


def record_from_managed(
    data: dict[str, Any],
    fetched_at: str,
) -> CanonicalRecord | None:
    name = str(data.get("name") or "").strip()
    website = str(data.get("official_website") or data.get("website") or "").strip() or None
    qid = data.get("wikidata")
    uskp = data.get("uskp")
    slug = npu_slug(website) or str(data.get("slug") or "").strip() or None
    if not slug and qid:
        slug = f"wikidata:{qid}"
    if not name or not slug:
        return None
    hours, tickets = visitor_urls(website)
    if data.get("opening_hours_url"):
        hours = str(data["opening_hours_url"])
    if data.get("ticket_url"):
        tickets = str(data["ticket_url"])
    external_ids: dict[str, str] = {SOURCE_TYPE: slug}
    if qid:
        external_ids["wikidata"] = str(qid)
    if uskp:
        external_ids["uskp"] = str(uskp)
    types = [str(code) for code in (data.get("types") or [])]
    if not types:
        types = types_from_labels([str(item) for item in (data.get("type_labels") or [])])
    return CanonicalRecord(
        source_type=SOURCE_TYPE,
        external_id=slug,
        external_ids=external_ids,
        name=name,
        types=types,
        official_website=website,
        opening_hours_url=hours,
        ticket_url=tickets,
        visitability=str(data.get("visitability") or "REGULAR"),
        municipality=data.get("municipality"),
        district=data.get("district"),
        region=data.get("region"),
        latitude=float(data["latitude"]) if data.get("latitude") is not None else None,
        longitude=float(data["longitude"]) if data.get("longitude") is not None else None,
        source_url=website,
        license=LICENSE,
        raw={"managed": data, "note": "no NPÚ article text or photos imported"},
        fetched_at=fetched_at,
    )


def records_from_managed_list(items: list[dict[str, Any]], fetched_at: str) -> list[CanonicalRecord]:
    records: list[CanonicalRecord] = []
    for item in items:
        record = record_from_managed(item, fetched_at)
        if record is not None:
            records.append(record)
    return records


def records_from_sparql(data: dict[str, Any], fetched_at: str) -> list[CanonicalRecord]:
    results = data.get("results") if isinstance(data, dict) else None
    bindings = results.get("bindings") if isinstance(results, dict) else None
    if not isinstance(bindings, list):
        raise ValueError("Neplatná SPARQL odpověď NPÚ objektů")
    items: list[dict[str, Any]] = []
    for binding in bindings:
        if not isinstance(binding, dict):
            continue
        qid = qid_from_uri((binding.get("item") or {}).get("value"))
        name = (binding.get("itemLabel") or {}).get("value")
        web = (binding.get("web") or {}).get("value")
        uskp = (binding.get("uskp") or {}).get("value")
        if not qid or not name:
            continue
        items.append(
            {
                "name": name,
                "wikidata": qid,
                "official_website": web,
                "uskp": uskp,
            }
        )
    return records_from_managed_list(items, fetched_at)
