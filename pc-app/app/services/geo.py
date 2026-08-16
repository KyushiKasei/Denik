"""Vzdálenost vzdušnou čarou a Nominatim reverse. Stejný Haversine jako pwa/src/geo/haversine.ts."""

from __future__ import annotations

from dataclasses import dataclass
from math import atan2, cos, radians, sin, sqrt
from typing import Any

from app.importers.http_client import DownloadError, fetch_json

EARTH_RADIUS_M = 6_371_000.0
METERS_PER_DEG_LAT = 111_320.0
KM_PER_DEG_LAT = METERS_PER_DEG_LAT / 1000.0
MIN_COS_LAT = 0.2

DEFAULT_RADIUS_KM = 30
MIN_RADIUS_KM = 5
MAX_RADIUS_KM = 150
RADIUS_STEP_KM = 5

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
NOMINATIM_REVERSE_URL = "https://nominatim.openstreetmap.org/reverse"


@dataclass(frozen=True)
class ReverseLocation:
    municipality: str | None = None
    district: str | None = None
    region: str | None = None
    address: str | None = None
    village: str | None = None
    municipality_candidates: tuple[str, ...] = ()


def distance_m(
    lat1: float | None,
    lon1: float | None,
    lat2: float | None,
    lon2: float | None,
) -> float | None:
    if None in (lat1, lon1, lat2, lon2):
        return None
    phi1, phi2 = radians(lat1), radians(lat2)  # type: ignore[arg-type]
    dphi = radians(lat2 - lat1)  # type: ignore[operator]
    dlmb = radians(lon2 - lon1)  # type: ignore[operator]
    a = sin(dphi / 2) ** 2 + cos(phi1) * cos(phi2) * sin(dlmb / 2) ** 2
    return 2 * EARTH_RADIUS_M * atan2(sqrt(a), sqrt(1 - a))


def haversine_km(
    lat1: float | None,
    lon1: float | None,
    lat2: float | None,
    lon2: float | None,
) -> float | None:
    meters = distance_m(lat1, lon1, lat2, lon2)
    if meters is None:
        return None
    return meters / 1000.0


def clamp_radius_km(raw: float | int | str | None) -> int:
    if raw is None or raw == "":
        return DEFAULT_RADIUS_KM
    try:
        value = int(round(float(str(raw).replace(",", "."))))
    except (TypeError, ValueError):
        return DEFAULT_RADIUS_KM
    return max(MIN_RADIUS_KM, min(MAX_RADIUS_KM, value))


def bounding_box(lat: float, lon: float, radius_km: float) -> tuple[float, float, float, float]:
    """min_lat, max_lat, min_lon, max_lon — hrubý řez před Haversine."""
    dlat = radius_km / KM_PER_DEG_LAT
    cos_lat = max(MIN_COS_LAT, abs(cos(radians(lat))))
    dlon = radius_km / (KM_PER_DEG_LAT * cos_lat)
    return lat - dlat, lat + dlat, lon - dlon, lon + dlon


def _clean_admin_name(value: str | None, *, strip_okres: bool = False) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    if strip_okres:
        lowered = text.casefold()
        if lowered.startswith("okres "):
            text = text[6:].strip()
    return text or None


def parse_nominatim_address(payload: dict[str, Any]) -> ReverseLocation | None:
    address = payload.get("address") if isinstance(payload, dict) else None
    if not isinstance(address, dict):
        return None
    village = _clean_admin_name(
        address.get("village") or address.get("hamlet") or address.get("suburb")
    )
    candidates: list[str] = []
    for key in ("municipality", "city", "town", "village", "hamlet"):
        name = _clean_admin_name(address.get(key))
        if name and name not in candidates:
            candidates.append(name)
    municipality = candidates[0] if candidates else None
    district = _clean_admin_name(address.get("county"), strip_okres=True)
    region = _clean_admin_name(address.get("state"))
    house = _clean_admin_name(address.get("house_number"))
    road = _clean_admin_name(address.get("road") or address.get("square"))
    if road and house:
        street_address = f"{road} {house}"
    elif village and house:
        street_address = f"{village} {house}"
    elif municipality and house:
        street_address = f"{municipality} {house}"
    else:
        street_address = None
    if not municipality and not district and not region and not street_address:
        return None
    return ReverseLocation(
        municipality=municipality,
        district=district,
        region=region,
        address=street_address,
        village=village,
        municipality_candidates=tuple(candidates),
    )


def reverse_nominatim(
    latitude: float,
    longitude: float,
    *,
    transport: Any = None,
) -> ReverseLocation | None:
    try:
        data = fetch_json(
            NOMINATIM_REVERSE_URL,
            params={
                "lat": f"{latitude:.6f}",
                "lon": f"{longitude:.6f}",
                "format": "json",
                "addressdetails": 1,
                "zoom": 18,
            },
            headers={"Accept-Language": "cs"},
            timeout=15.0,
            max_retries=2,
            transport=transport,
        )
    except DownloadError:
        return None
    if not isinstance(data, dict):
        return None
    return parse_nominatim_address(data)


__all__ = [
    "DEFAULT_RADIUS_KM",
    "EARTH_RADIUS_M",
    "KM_PER_DEG_LAT",
    "MAX_RADIUS_KM",
    "METERS_PER_DEG_LAT",
    "MIN_COS_LAT",
    "MIN_RADIUS_KM",
    "NOMINATIM_REVERSE_URL",
    "NOMINATIM_URL",
    "RADIUS_STEP_KM",
    "ReverseLocation",
    "bounding_box",
    "clamp_radius_km",
    "distance_m",
    "haversine_km",
    "parse_nominatim_address",
    "reverse_nominatim",
]
