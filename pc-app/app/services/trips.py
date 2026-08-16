"""Výlety v osobním deníku. Nezakládá Place."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Place, Trip, TripStop, now_iso
from app.ids import new_public_id
from app.logging_setup import get_logger
from app.services.diary_io import VisitInputError, _parse_visited_at
from app.services.geo import haversine_km

_log = get_logger()


class TripInputError(VisitInputError):
    """Neplatný formulář výletu."""


def list_trips(session: Session, *, include_deleted: bool = False) -> list[Trip]:
    stmt = select(Trip)
    if not include_deleted:
        stmt = stmt.where(Trip.deleted_at.is_(None))
    return list(session.scalars(stmt.order_by(Trip.planned_on.desc(), Trip.updated_at.desc())).all())


def get_trip(session: Session, public_id: str) -> Trip | None:
    return session.scalar(select(Trip).where(Trip.public_id == public_id))


def create_trip(
    session: Session,
    *,
    name: str,
    planned_on: str | None = None,
    notes: str | None = None,
    origin_latitude: float | None = None,
    origin_longitude: float | None = None,
    origin_label: str | None = None,
) -> Trip:
    title = (name or "").strip() or "Výlet"
    try:
        date_value = _parse_visited_at(planned_on) if planned_on else None
    except VisitInputError as exc:
        raise TripInputError(str(exc)) from exc
    now = now_iso()
    trip = Trip(
        public_id=new_public_id(),
        name=title,
        planned_on=date_value,
        notes=(notes or "").strip() or None,
        origin_latitude=origin_latitude,
        origin_longitude=origin_longitude,
        origin_label=(origin_label or "").strip() or None,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    session.add(trip)
    session.commit()
    session.refresh(trip)
    _log.info("trip created id=%s", trip.public_id)
    return trip


def update_trip(
    session: Session,
    trip: Trip,
    *,
    name: str,
    planned_on: str | None,
    notes: str | None,
) -> Trip:
    if trip.deleted_at:
        raise TripInputError("Smazaný výlet nelze upravit.")
    trip.name = (name or "").strip() or trip.name
    try:
        trip.planned_on = _parse_visited_at(planned_on) if planned_on else None
    except VisitInputError as exc:
        raise TripInputError(str(exc)) from exc
    trip.notes = (notes or "").strip() or None
    trip.updated_at = now_iso()
    session.commit()
    session.refresh(trip)
    return trip


def soft_delete_trip(session: Session, trip: Trip) -> Trip:
    if trip.deleted_at:
        return trip
    now = now_iso()
    trip.deleted_at = now
    trip.updated_at = now
    session.commit()
    return trip


def add_stop(session: Session, trip: Trip, place: Place) -> Trip:
    if trip.deleted_at:
        raise TripInputError("Smazaný výlet nelze upravit.")
    if any(stop.place_public_id == place.public_id for stop in trip.stops):
        return trip
    order = max((stop.sort_order for stop in trip.stops), default=-1) + 1
    trip.stops.append(
        TripStop(
            place_public_id=place.public_id,
            place_id=place.id,
            sort_order=order,
            note=None,
        )
    )
    trip.updated_at = now_iso()
    session.commit()
    session.refresh(trip)
    return trip


def remove_stop(session: Session, trip: Trip, place_public_id: str) -> Trip:
    for stop in list(trip.stops):
        if stop.place_public_id == place_public_id:
            session.delete(stop)
            trip.stops.remove(stop)
    remaining = sorted(trip.stops, key=lambda item: item.sort_order)
    for index, stop in enumerate(remaining):
        stop.sort_order = index
    trip.updated_at = now_iso()
    session.commit()
    session.refresh(trip)
    return trip


def move_stop(session: Session, trip: Trip, place_public_id: str, direction: int) -> Trip:
    stops = sorted(trip.stops, key=lambda item: item.sort_order)
    index = next((i for i, stop in enumerate(stops) if stop.place_public_id == place_public_id), -1)
    next_index = index + direction
    if index < 0 or next_index < 0 or next_index >= len(stops):
        return trip
    stops[index], stops[next_index] = stops[next_index], stops[index]
    for order, stop in enumerate(stops):
        stop.sort_order = order
    trip.updated_at = now_iso()
    session.commit()
    session.refresh(trip)
    return trip


def consecutive_stop_km(trip: Trip) -> list[float | None]:
    stops = sorted(trip.stops, key=lambda item: item.sort_order)
    gaps: list[float | None] = []
    for left, right in zip(stops, stops[1:]):
        from_place = left.place
        to_place = right.place
        if (
            from_place is None
            or to_place is None
            or from_place.latitude is None
            or from_place.longitude is None
            or to_place.latitude is None
            or to_place.longitude is None
        ):
            gaps.append(None)
            continue
        km = haversine_km(from_place.latitude, from_place.longitude, to_place.latitude, to_place.longitude)
        gaps.append(km)
    return gaps
