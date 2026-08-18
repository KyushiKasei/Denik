"""Jednotný význam zříceniny: typ RUIN nebo stav RUIN."""

from __future__ import annotations

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session

from app.db.models import Place, PlacePlaceType, PlaceType


def place_type_codes(place: Place) -> list[str]:
    return [item.code for item in place.types]


def is_ruin(place: Place) -> bool:
    return place.condition == "RUIN" or "RUIN" in place_type_codes(place)


def ruin_type_exists():
    return exists(
        select(1)
        .select_from(PlacePlaceType)
        .join(PlaceType, PlaceType.id == PlacePlaceType.place_type_id)
        .where(PlacePlaceType.place_id == Place.id, PlaceType.code == "RUIN")
    )


def is_ruin_clause():
    return or_(Place.condition == "RUIN", ruin_type_exists())


def ruin_union_count(session: Session) -> int:
    return (
        session.scalar(
            select(func.count()).select_from(Place).where(Place.archived_at.is_(None), is_ruin_clause())
        )
        or 0
    )
