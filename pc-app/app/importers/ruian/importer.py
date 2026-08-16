"""RÚIAN normalizace obce / okresu / kraje u existujících míst."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.config import REPO_ROOT, get_data_dir
from app.db.models import Place, now_iso
from app.importers.base import CanonicalRecord
from app.importers.ruian.client import RuianClient
from app.importers.ruian.parser import (
    RuianLookup,
    build_lookup,
    parse_codebook_text,
    record_for_place,
)
from app.logging_setup import get_logger
from app.services.geo import ReverseLocation, reverse_nominatim

SOURCE_TYPE = "ruian"
SAMPLE_DIR = REPO_ROOT / "fixtures" / "import" / "ruian"
NOMINATIM_MIN_INTERVAL_S = 1.1
_log = get_logger()
ReverseFn = Callable[[float, float], ReverseLocation | None]
ProgressFn = Callable[[int, int, str], None]


def cache_path() -> Path:
    return get_data_dir() / "cache" / "ruian_last.json"


def save_tables(tables: dict[str, list[dict[str, str]]]) -> Path:
    path = cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(tables, ensure_ascii=False), encoding="utf-8")
    return path


def load_tables_file(path: Path) -> dict[str, list[dict[str, str]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Neplatný RÚIAN cache: {path}")
    return {str(k): list(v) for k, v in data.items() if isinstance(v, list)}


def lookup_from_tables(tables: dict[str, list[dict[str, str]]]) -> RuianLookup:
    return RuianLookup(
        build_lookup(
            tables.get("obce") or [],
            tables.get("okresy") or [],
            tables.get("kraje") or [],
        )
    )


def lookup_from_sample_dir(path: Path | None = None) -> RuianLookup:
    folder = path or SAMPLE_DIR
    obce = parse_codebook_text((folder / "obce.csv").read_text(encoding="utf-8"))
    okresy = parse_codebook_text((folder / "okresy.csv").read_text(encoding="utf-8"))
    kraje = parse_codebook_text((folder / "kraje.csv").read_text(encoding="utf-8"))
    return lookup_from_tables({"obce": obce, "okresy": okresy, "kraje": kraje})


def reverse_cache_path() -> Path:
    return get_data_dir() / "cache" / "nominatim_reverse.json"


def _place_external_ids(place: Place) -> dict[str, str]:
    return {
        source.source_type: source.external_id
        for source in place.sources
        if source.external_id
    }


def _needs_reverse(place: Place) -> bool:
    return (
        not place.municipality
        and place.latitude is not None
        and place.longitude is not None
    )


def match_reverse_location(lookup: RuianLookup, loc: ReverseLocation):
    for name in loc.municipality_candidates or ((loc.municipality,) if loc.municipality else ()):
        hit = lookup.match(name, loc.district, loc.region)
        if hit is not None:
            return hit
    return None


def _record_kwargs(place: Place) -> dict[str, Any]:
    return {
        "name": place.name,
        "external_ids": _place_external_ids(place),
        "latitude": place.latitude,
        "longitude": place.longitude,
        "types": [item.code for item in place.types],
    }


def records_for_places(
    places: list[Place],
    lookup: RuianLookup,
    fetched_at: str | None = None,
    *,
    reverse_fn: ReverseFn | None = None,
    on_progress: ProgressFn | None = None,
) -> list[CanonicalRecord]:
    when = fetched_at or now_iso()
    records: list[CanonicalRecord] = []
    missing = [place for place in places if not place.archived_at and _needs_reverse(place)]
    reversed_done = 0
    for place in places:
        if place.archived_at:
            continue
        hit = lookup.match(place.municipality, place.district, place.region)
        loc: ReverseLocation | None = None
        if hit is None and reverse_fn is not None and _needs_reverse(place):
            reversed_done += 1
            if on_progress:
                on_progress(reversed_done, len(missing), place.name)
            loc = reverse_fn(place.latitude, place.longitude)  # type: ignore[arg-type]
            if loc is not None:
                hit = match_reverse_location(lookup, loc)
        if hit is None and loc is None:
            continue
        if hit is None and loc is not None and not (loc.municipality or loc.district or loc.region or loc.address):
            continue
        records.append(
            record_for_place(
                **_record_kwargs(place),
                hit=hit,
                fetched_at=when,
                address=None if hit is not None and loc is None else (loc.address if loc else None),
                municipality=None if hit is not None else loc.municipality if loc else None,
                district=None if hit is not None else loc.district if loc else None,
                region=None if hit is not None else loc.region if loc else None,
                raw_extra={"reverse": "nominatim"} if loc is not None else None,
            )
        )
    return records


class _CachedReverse:
    def __init__(self, *, transport: Any = None, sleep: Any = time.sleep) -> None:
        self.transport = transport
        self.sleep = sleep
        self._last_request = 0.0
        self._cache = self._load()

    def _load(self) -> dict[str, dict[str, Any]]:
        path = reverse_cache_path()
        if not path.is_file():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _save(self) -> None:
        path = reverse_cache_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self._cache, ensure_ascii=False), encoding="utf-8")

    def __call__(self, latitude: float, longitude: float) -> ReverseLocation | None:
        key = f"{latitude:.4f},{longitude:.4f}"
        cached = self._cache.get(key)
        if isinstance(cached, dict):
            if cached.get("empty"):
                return None
            loc = ReverseLocation(
                municipality=cached.get("municipality"),
                district=cached.get("district"),
                region=cached.get("region"),
                address=cached.get("address"),
                village=cached.get("village"),
                municipality_candidates=tuple(cached.get("municipality_candidates") or ()),
            )
            return loc
        wait = NOMINATIM_MIN_INTERVAL_S - (time.monotonic() - self._last_request)
        if wait > 0:
            self.sleep(wait)
        loc = reverse_nominatim(latitude, longitude, transport=self.transport)
        self._last_request = time.monotonic()
        if loc is None:
            self._cache[key] = {"empty": True}
        else:
            self._cache[key] = {
                "municipality": loc.municipality,
                "district": loc.district,
                "region": loc.region,
                "address": loc.address,
                "village": loc.village,
                "municipality_candidates": list(loc.municipality_candidates),
            }
        self._save()
        return loc


def fetch_ruian_records(
    session: Session,
    *,
    use_cache: bool = False,
    client: RuianClient | None = None,
    reverse_fn: ReverseFn | None = None,
    on_progress: ProgressFn | None = None,
    skip_reverse: bool = False,
) -> list[CanonicalRecord]:
    tables = None
    if use_cache:
        path = cache_path()
        if path.is_file():
            tables = load_tables_file(path)
            _log.info("ruian loaded from cache")
    if tables is None:
        client = client or RuianClient()
        tables = client.fetch_tables()
        save_tables(tables)
    lookup = lookup_from_tables(tables)
    places = list(session.scalars(select(Place).where(Place.archived_at.is_(None))).all())
    if reverse_fn is None and not skip_reverse:
        reverse_fn = _CachedReverse()
    records = records_for_places(places, lookup, reverse_fn=reverse_fn, on_progress=on_progress)
    _log.info("ruian records=%s of places=%s", len(records), len(places))
    return records
