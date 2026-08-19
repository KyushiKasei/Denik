"""Veřejné URL identity zdroje (Wikidata, Wikipedia, ÚSKP, OSM)."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote


def is_http_url(value: Any) -> bool:
    return isinstance(value, str) and value.startswith(("http://", "https://"))


def photo_display_url(photo: Any) -> str | None:
    """Veřejné URL náhledu: thumbnail, jinak originál / source. Bere PlacePhoto i dict z importu."""
    if photo is None:
        return None
    values: list[Any] = []
    if isinstance(photo, dict):
        values = [photo.get("thumbnail_url"), photo.get("original_url"), photo.get("source_url")]
    else:
        values = [getattr(photo, "thumbnail_url", None), getattr(photo, "original_url", None), getattr(photo, "source_url", None)]
    for value in values:
        if is_http_url(value):
            return str(value).strip()
    return None


def identity_source_url(source_type: str | None, external_id: str | None) -> str | None:
    """Sestaví stránku zdroje z typu a externího ID. None, když nevíme."""
    if not source_type or not external_id:
        return None
    kind = source_type.strip().lower()
    ident = str(external_id).strip()
    if not ident:
        return None
    if kind == "wikidata" and ident[:1] == "Q" and ident[1:].isdigit():
        return f"https://www.wikidata.org/wiki/{ident}"
    if kind == "wikipedia":
        lang, sep, title = ident.partition(":")
        if sep and lang and title:
            page = quote(title.replace(" ", "_"), safe="()_,-")
            return f"https://{lang}.wikipedia.org/wiki/{page}"
        return None
    if kind == "uskp":
        return f"https://pamatkovykatalog.cz/uskp/{quote(ident, safe='_-')}"
    if kind == "pamatkovy_katalog":
        return f"https://pamatkovykatalog.cz/{quote(ident, safe='_-')}"
    if kind == "osm":
        return f"https://www.openstreetmap.org/{ident.lstrip('/')}"
    return None


def source_page_url(source: Any) -> str | None:
    """Klikací URL karty zdroje: odvozené z identity, jinak uložené source_url."""
    stored = getattr(source, "source_url", None)
    built = identity_source_url(
        getattr(source, "source_type", None),
        getattr(source, "external_id", None),
    )
    return built or (stored if is_http_url(stored) else None)
