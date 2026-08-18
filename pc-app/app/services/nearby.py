"""Poblíž: origin + radius nad SQLite katalogem. Nic nezapisuje."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.db.models import Place
from app.importers.http_client import DownloadError, fetch_json
from app.services.geo import NOMINATIM_URL, bounding_box, clamp_radius_km, haversine_km
from app.services.matching import normalize_name
from app.services.places import PlaceFilters, _apply_filters, parse_coord


@dataclass(frozen=True)
class Origin:
    latitude: float
    longitude: float
    label: str
    source: str  # coords | place | municipality | nominatim


@dataclass
class NearbyHit:
    place: Place
    km: float
    visited: bool
    want_to_visit: bool


MAX_NEARBY_HITS = 200


@dataclass
class NearbyResult:
    origin: Origin | None
    radius_km: int
    hits: list[NearbyHit]
    skipped_no_gps: int
    error: str | None = None
    hits_total: int = 0


def _parse_optional_coord(raw: Any, kind: str) -> float | None:
    value, err = parse_coord(raw, kind)
    if err:
        return None
    return value


def origin_from_coords(
    lat_raw: Any,
    lon_raw: Any,
    label: str | None = None,
) -> Origin | None:
    lat = _parse_optional_coord(lat_raw, "latitude")
    lon = _parse_optional_coord(lon_raw, "longitude")
    if lat is None or lon is None:
        return None
    text = (label or "").strip() or f"{lat:.5f}, {lon:.5f}"
    return Origin(latitude=lat, longitude=lon, label=text, source="coords")


def suggest_origins(session: Session, q: str, *, limit: int = 8) -> list[Origin]:
    term = (q or "").strip()
    if len(term) < 2:
        return []
    like = f"%{term}%"
    places = list(
        session.scalars(
            select(Place)
            .where(
                Place.archived_at.is_(None),
                Place.latitude.is_not(None),
                Place.longitude.is_not(None),
                or_(
                    Place.name.ilike(like),
                    Place.short_name.ilike(like),
                    Place.municipality.ilike(like),
                    Place.alternative_names.ilike(like),
                ),
            )
            .order_by(Place.name.asc())
            .limit(limit)
        ).all()
    )
    seen: set[tuple[float, float, str]] = set()
    out: list[Origin] = []
    for place in places:
        if place.latitude is None or place.longitude is None:
            continue
        key = (place.latitude, place.longitude, place.public_id)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            Origin(
                latitude=place.latitude,
                longitude=place.longitude,
                label=place.name,
                source="place",
            )
        )
    return out


def _origin_from_place(place: Place, *, source: str, label: str | None = None) -> Origin | None:
    if place.latitude is None or place.longitude is None:
        return None
    return Origin(
        latitude=place.latitude,
        longitude=place.longitude,
        label=label or place.name,
        source=source,
    )


def resolve_origin_from_catalog(session: Session, q: str) -> Origin | None:
    term = (q or "").strip()
    if not term:
        return None
    needle = normalize_name(term)
    if not needle:
        return None

    places = list(
        session.scalars(
            select(Place)
            .where(
                Place.archived_at.is_(None),
                Place.latitude.is_not(None),
                Place.longitude.is_not(None),
            )
            .order_by(Place.name.asc())
        ).all()
    )

    exact_name = [p for p in places if normalize_name(p.name) == needle]
    if exact_name:
        return _origin_from_place(exact_name[0], source="place")

    exact_muni = [p for p in places if normalize_name(p.municipality or "") == needle]
    if exact_muni:
        place = exact_muni[0]
        return _origin_from_place(place, source="municipality", label=place.municipality or place.name)

    starts = [p for p in places if normalize_name(p.name).startswith(needle)]
    if starts:
        return _origin_from_place(starts[0], source="place")

    contains = [p for p in places if needle in normalize_name(p.name)]
    if contains:
        return _origin_from_place(contains[0], source="place")

    return None


def geocode_nominatim(
    q: str,
    *,
    transport: Any = None,
) -> Origin | None:
    term = (q or "").strip()
    if len(term) < 2:
        return None
    try:
        data = fetch_json(
            NOMINATIM_URL,
            params={
                "q": term,
                "format": "json",
                "limit": 1,
                "countrycodes": "cz",
            },
            headers={"Accept-Language": "cs"},
            timeout=15.0,
            max_retries=2,
            transport=transport,
        )
    except DownloadError:
        return None
    if not isinstance(data, list) or not data:
        return None
    row = data[0]
    try:
        lat = float(row["lat"])
        lon = float(row["lon"])
    except (KeyError, TypeError, ValueError):
        return None
    label = str(row.get("display_name") or term)
    return Origin(latitude=lat, longitude=lon, label=label, source="nominatim")


def resolve_origin(
    session: Session,
    *,
    lat: Any = None,
    lon: Any = None,
    q: str = "",
    origin_label: str = "",
    geocode: bool = True,
    transport: Any = None,
) -> Origin | None:
    from_coords = origin_from_coords(lat, lon, origin_label or q)
    if from_coords is not None:
        if origin_label.strip():
            return Origin(from_coords.latitude, from_coords.longitude, origin_label.strip(), from_coords.source)
        return from_coords
    catalog = resolve_origin_from_catalog(session, q)
    if catalog is not None:
        return catalog
    if geocode and (q or "").strip():
        return geocode_nominatim(q, transport=transport)
    return None


def count_missing_gps(session: Session) -> int:
    return (
        session.scalar(
            select(func.count())
            .select_from(Place)
            .where(
                Place.archived_at.is_(None),
                or_(Place.latitude.is_(None), Place.longitude.is_(None)),
            )
        )
        or 0
    )


def list_nearby(
    session: Session,
    origin: Origin,
    *,
    radius_km: int | float | str | None = None,
    type_code: str = "",
    visitability: str = "",
    journal: str = "",
) -> NearbyResult:
    radius = clamp_radius_km(radius_km)
    skipped = count_missing_gps(session)
    filters = PlaceFilters(
        type_code=type_code.strip(),
        visitability=visitability.strip(),
        journal=journal.strip(),
        archived="active",
        worth=False,
    )
    min_lat, max_lat, min_lon, max_lon = bounding_box(origin.latitude, origin.longitude, radius)
    stmt = _apply_filters(select(Place), filters).where(
        Place.latitude.is_not(None),
        Place.longitude.is_not(None),
        Place.latitude >= min_lat,
        Place.latitude <= max_lat,
        Place.longitude >= min_lon,
        Place.longitude <= max_lon,
    )
    places = list(session.scalars(stmt).all())
    hits: list[NearbyHit] = []
    for place in places:
        km = haversine_km(origin.latitude, origin.longitude, place.latitude, place.longitude)
        if km is None or km > radius:
            continue
        visited = any(visit.deleted_at is None for visit in place.visits)
        want = bool(place.journal_state and place.journal_state.want_to_visit and not place.journal_state.deleted_at)
        hits.append(NearbyHit(place=place, km=km, visited=visited, want_to_visit=want))
    hits.sort(key=lambda item: (item.km, item.place.name.lower()))
    total = len(hits)
    return NearbyResult(
        origin=origin,
        radius_km=radius,
        hits=hits[:MAX_NEARBY_HITS],
        skipped_no_gps=skipped,
        hits_total=total,
    )
