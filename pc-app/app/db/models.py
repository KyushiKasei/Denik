from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.ids import new_public_id


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class Base(DeclarativeBase):
    pass


class PlaceType(Base):
    __tablename__ = "place_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name_cs: Mapped[str] = mapped_column(String(80), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    places: Mapped[list["Place"]] = relationship(
        secondary="place_place_types",
        back_populates="types",
    )


class Place(Base):
    __tablename__ = "places"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, default=new_public_id)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    short_name: Mapped[str | None] = mapped_column(String(120))
    alternative_names: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    short_description: Mapped[str | None] = mapped_column(Text)
    condition: Mapped[str] = mapped_column(String(32), nullable=False, default="UNKNOWN")
    visitability: Mapped[str] = mapped_column(String(32), nullable=False, default="UNKNOWN")
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    address: Mapped[str | None] = mapped_column(String(400))
    municipality: Mapped[str | None] = mapped_column(String(120))
    municipality_code: Mapped[str | None] = mapped_column(String(20))
    district: Mapped[str | None] = mapped_column(String(120))
    district_code: Mapped[str | None] = mapped_column(String(20))
    region: Mapped[str | None] = mapped_column(String(120))
    region_code: Mapped[str | None] = mapped_column(String(20))
    country: Mapped[str] = mapped_column(String(8), nullable=False, default="CZ")
    official_website: Mapped[str | None] = mapped_column(String(500))
    wikipedia_url: Mapped[str | None] = mapped_column(String(500))
    opening_hours_url: Mapped[str | None] = mapped_column(String(500))
    ticket_url: Mapped[str | None] = mapped_column(String(500))
    heritage_status: Mapped[str | None] = mapped_column(String(32))
    unesco: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quality_status: Mapped[str] = mapped_column(String(32), nullable=False, default="NEEDS_REVIEW")
    created_at: Mapped[str] = mapped_column(String(40), nullable=False, default=now_iso)
    updated_at: Mapped[str] = mapped_column(String(40), nullable=False, default=now_iso, onupdate=now_iso)
    archived_at: Mapped[str | None] = mapped_column(String(40))

    types: Mapped[list[PlaceType]] = relationship(
        secondary="place_place_types",
        back_populates="places",
        lazy="selectin",
        order_by="PlaceType.sort_order",
    )

    @property
    def is_archived(self) -> bool:
        return self.archived_at is not None

    @property
    def has_gps(self) -> bool:
        return self.latitude is not None and self.longitude is not None

    @property
    def alt_names(self) -> list[str]:
        try:
            data = json.loads(self.alternative_names or "[]")
        except json.JSONDecodeError:
            return []
        return [str(item) for item in data] if isinstance(data, list) else []

    @property
    def types_cs(self) -> str:
        names = [item.name_cs for item in self.types]
        return ", ".join(names) if names else "—"


class PlacePlaceType(Base):
    __tablename__ = "place_place_types"
    __table_args__ = (UniqueConstraint("place_id", "place_type_id"),)

    place_id: Mapped[int] = mapped_column(ForeignKey("places.id"), primary_key=True)
    place_type_id: Mapped[int] = mapped_column(ForeignKey("place_types.id"), primary_key=True)


class AppMeta(Base):
    __tablename__ = "app_meta"

    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)


@event.listens_for(Place.public_id, "set", retval=True)
def _forbid_public_id_change(target: Place, value: str, oldvalue: str, initiator) -> str:
    from sqlalchemy.orm.attributes import NEVER_SET, NO_VALUE

    if oldvalue not in (None, NEVER_SET, NO_VALUE) and oldvalue != value:
        raise ValueError("Place.public_id is immutable and must never be changed")
    return value
