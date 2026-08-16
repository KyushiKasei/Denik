"""Export master katalogu do catalog.json. Integer places.id se do JSON nedostane."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_default_catalog_path
from app.db.models import AppMeta, Place, PlacePhoto, now_iso
from app.logging_setup import get_logger
from app.services.catalog_schema import SCHEMA_VERSION, validate_catalog
from app.services.source_urls import is_http_url, source_page_url

_log = get_logger()

META_VERSION = "catalog_version"
META_HASH = "last_catalog_content_hash"
META_EXPORT_AT = "last_catalog_export_at"

CATALOG_ATTRIBUTION = {
    "wikidata": "Wikidata contributors, CC0",
    "npu_opendata": "Geoportál památkové péče, Národní památkový ústav, CC BY-SA 4.0",
    "osm": "© OpenStreetMap contributors, ODbL",
    "commons": "Licence u jednotlivých fotografií",
}


@dataclass(frozen=True)
class CatalogExportResult:
    path: Path
    catalog_version: int
    place_count: int
    content_changed: bool
    content_hash: str
    catalog: dict[str, Any]


def _get_meta(session: Session, key: str) -> str | None:
    row = session.get(AppMeta, key)
    return row.value if row is not None else None


def _set_meta(session: Session, key: str, value: str) -> None:
    row = session.get(AppMeta, key)
    if row is None:
        session.add(AppMeta(key=key, value=value))
    else:
        row.value = value


def catalog_export_status(session: Session) -> dict[str, Any]:
    version_raw = _get_meta(session, META_VERSION)
    return {
        "catalog_version": int(version_raw) if version_raw else 0,
        "last_export_at": _get_meta(session, META_EXPORT_AT),
        "last_content_hash": _get_meta(session, META_HASH),
        "default_path": get_default_catalog_path(),
    }


def _http_or_none(value: str | None) -> str | None:
    text = (value or "").strip()
    return text if is_http_url(text) else None


def _source_link(place: Place, *source_types: str) -> str | None:
    by_type = {item.source_type: item for item in place.sources}
    for kind in source_types:
        source = by_type.get(kind)
        if source is None:
            continue
        url = source_page_url(source)
        if url:
            return url
    return None


def _catalog_links(place: Place) -> dict[str, str | None]:
    return {
        "official": _http_or_none(place.official_website),
        "wikipedia": _http_or_none(place.wikipedia_url) or _source_link(place, "wikipedia"),
        "wikidata": _source_link(place, "wikidata"),
        "heritage_catalog": _source_link(place, "pamatkovy_katalog", "uskp"),
        "opening_hours": _http_or_none(place.opening_hours_url),
        "tickets": _http_or_none(place.ticket_url),
    }


def _pick_photo(place: Place) -> PlacePhoto | None:
    photos = list(place.photos)
    if not photos:
        return None
    photos.sort(key=lambda item: (0 if item.is_primary else 1, item.id))
    return photos[0]


def _catalog_image(place: Place) -> dict[str, str | None] | None:
    photo = _pick_photo(place)
    if photo is None:
        return None
    image = {
        "thumbnail_url": _http_or_none(photo.thumbnail_url),
        "original_url": _http_or_none(photo.original_url) or _http_or_none(photo.source_url),
        "attribution": (photo.attribution or "").strip() or None,
        "license": (photo.license or "").strip() or None,
        "license_url": _http_or_none(photo.license_url),
    }
    if image["thumbnail_url"] is None and image["original_url"] is None:
        return None
    return image


def place_to_catalog_item(place: Place) -> dict[str, Any]:
    """Master hodnoty Place. id = public_id, nikdy integer PK."""
    return {
        "id": place.public_id,
        "name": place.name,
        "short_name": place.short_name or None,
        "alternative_names": list(dict.fromkeys(place.alt_names)),
        "types": list(dict.fromkeys(item.code for item in place.types)),
        "condition": place.condition,
        "visitability": place.visitability,
        "short_description": place.short_description or None,
        "heritage_status": place.heritage_status or None,
        "unesco": bool(place.unesco),
        "location": {
            "latitude": place.latitude,
            "longitude": place.longitude,
            "address": place.address or None,
            "municipality": place.municipality or None,
            "district": place.district or None,
            "region": place.region or None,
            "country": place.country or "CZ",
        },
        "links": _catalog_links(place),
        "image": _catalog_image(place),
    }


def canonical_places_hash(places: list[dict[str, Any]]) -> str:
    payload = json.dumps(places, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def list_export_places(session: Session) -> list[Place]:
    return list(
        session.scalars(
            select(Place).where(Place.archived_at.is_(None)).order_by(Place.public_id)
        ).all()
    )


def _next_version(session: Session, content_hash: str) -> tuple[int, bool]:
    previous_hash = _get_meta(session, META_HASH)
    raw_version = _get_meta(session, META_VERSION)
    current = int(raw_version) if raw_version else 0
    if previous_hash == content_hash and current >= 1:
        return current, False
    return current + 1, True


def build_catalog(session: Session, *, persist_version: bool = True) -> dict[str, Any]:
    items = [place_to_catalog_item(place) for place in list_export_places(session)]
    content_hash = canonical_places_hash(items)
    version, changed = _next_version(session, content_hash)
    generated_at = now_iso()
    catalog = {
        "schema_version": SCHEMA_VERSION,
        "catalog_version": version,
        "generated_at": generated_at,
        "attribution": dict(CATALOG_ATTRIBUTION),
        "places": items,
    }
    validate_catalog(catalog)
    if persist_version:
        _set_meta(session, META_VERSION, str(version))
        _set_meta(session, META_HASH, content_hash)
        _set_meta(session, META_EXPORT_AT, generated_at)
        session.flush()
    catalog["_content_hash"] = content_hash
    catalog["_content_changed"] = changed
    return catalog


def _public_catalog(catalog: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in catalog.items() if not key.startswith("_")}


def dump_catalog_json(catalog: dict[str, Any]) -> str:
    return json.dumps(_public_catalog(catalog), ensure_ascii=False, indent=2) + "\n"


def export_catalog(session: Session, path: Path | None = None) -> CatalogExportResult:
    destination = path or get_default_catalog_path()
    catalog = build_catalog(session, persist_version=True)
    public = _public_catalog(catalog)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(dump_catalog_json(catalog), encoding="utf-8")
    session.commit()
    result = CatalogExportResult(
        path=destination,
        catalog_version=int(public["catalog_version"]),
        place_count=len(public["places"]),
        content_changed=bool(catalog["_content_changed"]),
        content_hash=str(catalog["_content_hash"]),
        catalog=public,
    )
    _log.info(
        "catalog exported path=%s version=%s places=%s changed=%s",
        destination,
        result.catalog_version,
        result.place_count,
        result.content_changed,
    )
    return result
