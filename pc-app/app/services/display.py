"""Zobrazení názvů a importních důvodů v PC UI. Master v DB se nemění."""

from __future__ import annotations

import json
import re

_DIST_RE = re.compile(r"distance=([0-9.]+)m")
_SIM_RE = re.compile(r"similarity=([0-9.]+)")


def display_place_name(name: str | None) -> str:
    trimmed = (name or "").strip()
    if not trimmed:
        return name or ""
    first = trimmed[0]
    upper = first.upper()
    if first == upper:
        return trimmed
    return f"{upper}{trimmed[1:]}"


def incoming_review_label(raw_data: str | None) -> str:
    """Název importovaného objektu z raw_data review, volitelně s obcí."""
    try:
        data = json.loads(raw_data or "{}")
    except json.JSONDecodeError:
        return "—"
    if not isinstance(data, dict):
        return "—"
    name = str(data.get("name") or "").strip() or "—"
    municipality = str(data.get("municipality") or "").strip()
    if municipality and municipality.casefold() not in name.casefold():
        return f"{name} ({municipality})"
    return name


def _meters(raw: str) -> str | None:
    try:
        meters = float(raw)
    except ValueError:
        return None
    if meters >= 10:
        return f"{int(round(meters))}\u00a0m"
    if meters >= 1:
        return f"{meters:.1f}\u00a0m".replace(".0\u00a0", "\u00a0")
    return f"{meters:.1f}\u00a0m"


def _name_likeness(raw: str) -> str | None:
    try:
        value = float(raw)
    except ValueError:
        return None
    if value >= 0.999:
        return "názvy jsou stejné"
    return f"názvy se podobají z {int(round(value * 100))}\u00a0%"


def _chunk_explanation(chunk: str) -> str | None:
    text = chunk.strip()
    if not text:
        return None
    dist = _DIST_RE.search(text)
    sim = _SIM_RE.search(text)
    dist_bit = _meters(dist.group(1)) if dist else None
    name_bit = _name_likeness(sim.group(1)) if sim else None

    if text.startswith("C1"):
        parts = [f"Blízko na mapě ({dist_bit})" if dist_bit else "Blízko na mapě"]
        if name_bit:
            parts.append(name_bit)
        return ", ".join(parts)
    if text.startswith("C2"):
        parts = ["Jsou ve stejné obci"]
        if name_bit:
            parts.append(name_bit)
        return ", ".join(parts)
    if text.startswith("B1"):
        parts = []
        if dist_bit:
            parts.append(f"velmi blízko ({dist_bit})")
        if name_bit:
            parts.append(name_bit)
        parts.append("obec i typy sedí")
        return ", ".join(parts).capitalize()
    if text.startswith("B2"):
        return "Stejný název, stejná obec" + (f", {dist_bit}" if dist_bit else "")
    if text.startswith("B3"):
        return "Stejný název, stejný okres" + (f", {dist_bit}" if dist_bit else "")
    if text.startswith("B4"):
        return "Stejný konkrétní název, typy sedí" + (f", {dist_bit}" if dist_bit else "")
    if text.startswith("B5"):
        gps = dist_bit if dist_bit else ("bez GPS" if "no_gps" in text else None)
        return "Stejný konkrétní název, stejná obec, typy sedí" + (f", {gps}" if gps else "")
    if text.startswith("A:"):
        return "Stejné ID zdroje nebo stejná fotka patří k více místům v katalogu, proto se neslučuje samo."
    if text.startswith("B:"):
        return "V katalogu vyhovuje víc míst pravděpodobné shodě, proto se neslučuje samo."
    return text


def explain_match_reason(reason: str | None, candidate_count: int = 1) -> str:
    """Technický match_reason (C1/C2/…) jako věta pro UI."""
    text = (reason or "").strip()
    if not text:
        return "Není jasné, jestli jde o stejné místo."

    chunks = [part.strip() for part in text.split(";") if part.strip()]
    explained = [item for item in (_chunk_explanation(chunk) for chunk in chunks) if item]
    if not explained:
        explained = [text]

    joined = "; ".join(explained)
    if any(chunk.startswith(("C1", "C2")) for chunk in chunks):
        if "neslučuje" not in joined and "Nestačí" not in joined:
            joined += ". Nestačí to k automatickému sloučení."
    if candidate_count > 1 and "víc míst" not in joined.lower() and "více míst" not in joined.lower():
        joined += f" V katalogu jsou {candidate_count} podobná místa."
    return joined


def format_distance_m(
    lat1: float | None,
    lon1: float | None,
    lat2: float | None,
    lon2: float | None,
) -> str | None:
    from app.services.geo import distance_m

    dist = distance_m(lat1, lon1, lat2, lon2)
    if dist is None:
        return None
    if dist >= 10:
        return f"{int(round(dist))}\u00a0m"
    return f"{dist:.1f}\u00a0m"


def incoming_is_sparse(record: dict | None) -> bool:
    """Import bez popisu, fotky i Wikipedie — k rozhodnutí zbývá hlavně mapa."""
    if not isinstance(record, dict):
        return True
    image = record.get("image")
    has_image = isinstance(image, dict) and any(image.get(key) for key in ("thumbnail_url", "original_url", "source_url"))
    return not any(
        (
            str(record.get("wikipedia_url") or "").strip(),
            str(record.get("official_website") or "").strip(),
            str(record.get("short_description") or "").strip(),
            has_image,
        )
    )


def record_source_id(record: dict | None, source_type: str) -> str | None:
    if not isinstance(record, dict) or not source_type:
        return None
    ids = record.get("external_ids") if isinstance(record.get("external_ids"), dict) else {}
    value = ids.get(source_type)
    if value:
        return str(value).strip() or None
    if str(record.get("source_type") or "") == source_type:
        ident = str(record.get("external_id") or "").strip()
        return ident or None
    return None


def place_source_id(place: object | None, source_type: str) -> str | None:
    if place is None:
        return None
    for source in getattr(place, "sources", ()) or ():
        if getattr(source, "source_type", None) == source_type and getattr(source, "external_id", None):
            return str(source.external_id).strip()
    return None


def _wiki_key(value: str | None) -> str:
    text = (value or "").strip()
    if not text:
        return ""
    if "/wiki/" in text:
        text = text.rsplit("/wiki/", 1)[-1]
    return text.replace(" ", "_").casefold()


def identity_conflicts(record: dict | None, place: object | None) -> list[str]:
    """Různá Wikidata / ÚSKP / Wikipedia = dvě entity, ne duplicita názvu."""
    conflicts: list[str] = []
    for source_type, label in (("wikidata", "Wikidata"), ("uskp", "ÚSKP")):
        left = record_source_id(record, source_type)
        right = place_source_id(place, source_type)
        if left and right and left != right:
            conflicts.append(f"{label} {left} vs {right}")
    incoming_wiki = _wiki_key((record or {}).get("wikipedia_url") if isinstance(record, dict) else None) or _wiki_key(
        record_source_id(record, "wikipedia")
    )
    catalog_wiki = _wiki_key(getattr(place, "wikipedia_url", None)) or _wiki_key(place_source_id(place, "wikipedia"))
    if incoming_wiki and catalog_wiki and incoming_wiki != catalog_wiki:
        conflicts.append("různé články na Wikipedii")
    return conflicts
