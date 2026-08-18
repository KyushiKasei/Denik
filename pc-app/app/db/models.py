from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, event, text
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
    osm_opening_hours: Mapped[str | None] = mapped_column(String(500))
    phone: Mapped[str | None] = mapped_column(String(80))
    fee: Mapped[str | None] = mapped_column(String(40))
    wheelchair: Mapped[str | None] = mapped_column(String(40))
    parking: Mapped[str | None] = mapped_column(String(80))
    visit_duration_minutes: Mapped[int | None] = mapped_column(Integer)
    last_entry: Mapped[str | None] = mapped_column(String(40))
    dogs: Mapped[str | None] = mapped_column(String(40))
    payment: Mapped[str | None] = mapped_column(String(40))
    amenities: Mapped[str] = mapped_column(Text, nullable=False, default="[]", server_default="[]")
    inception_year: Mapped[int | None] = mapped_column(Integer)
    architectural_style: Mapped[str | None] = mapped_column(String(120))
    heritage_status: Mapped[str | None] = mapped_column(String(32))
    unesco: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    quality_status: Mapped[str] = mapped_column(String(32), nullable=False, default="NEEDS_REVIEW")
    created_at: Mapped[str] = mapped_column(String(40), nullable=False, default=now_iso)
    updated_at: Mapped[str] = mapped_column(String(40), nullable=False, default=now_iso, onupdate=now_iso)
    archived_at: Mapped[str | None] = mapped_column(String(40))
    merged_into_public_id: Mapped[str | None] = mapped_column(String(36))

    types: Mapped[list[PlaceType]] = relationship(
        secondary="place_place_types",
        back_populates="places",
        lazy="selectin",
        order_by=PlaceType.sort_order,
    )
    sources: Mapped[list["PlaceSource"]] = relationship(
        back_populates="place",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    field_overrides: Mapped[list["PlaceFieldOverride"]] = relationship(
        back_populates="place",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    photos: Mapped[list["PlacePhoto"]] = relationship(
        back_populates="place",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    visits: Mapped[list["Visit"]] = relationship(
        back_populates="place",
        lazy="selectin",
    )
    journal_state: Mapped["PlaceJournalState | None"] = relationship(
        back_populates="place",
        uselist=False,
        lazy="selectin",
    )

    @property
    def is_archived(self) -> bool:
        return self.archived_at is not None

    @property
    def has_gps(self) -> bool:
        return self.latitude is not None and self.longitude is not None

    @property
    def primary_photo(self) -> PlacePhoto | None:
        photos = list(self.photos)
        if not photos:
            return None
        photos.sort(key=lambda item: (0 if item.is_primary else 1, item.id))
        return photos[0]

    @property
    def alt_names(self) -> list[str]:
        try:
            data = json.loads(self.alternative_names or "[]")
        except json.JSONDecodeError:
            return []
        return [str(item) for item in data] if isinstance(data, list) else []

    @property
    def amenity_codes(self) -> list[str]:
        try:
            data = json.loads(self.amenities or "[]")
        except json.JSONDecodeError:
            return []
        if not isinstance(data, list):
            return []
        return [str(item) for item in data if item]

    @property
    def types_cs(self) -> str:
        from app.db.enums import format_types

        return format_types([item.code for item in self.types])

    @property
    def is_visited(self) -> bool:
        return any(visit.deleted_at is None for visit in self.visits)

    @property
    def wants_visit(self) -> bool:
        state = self.journal_state
        return bool(state is not None and not state.is_deleted and state.want_to_visit)

    @property
    def is_favorite(self) -> bool:
        state = self.journal_state
        return bool(state is not None and not state.is_deleted and state.favorite)


class PlacePlaceType(Base):
    __tablename__ = "place_place_types"
    __table_args__ = (UniqueConstraint("place_id", "place_type_id"),)

    place_id: Mapped[int] = mapped_column(ForeignKey("places.id"), primary_key=True)
    place_type_id: Mapped[int] = mapped_column(ForeignKey("place_types.id"), primary_key=True)


class PlaceSource(Base):
    __tablename__ = "place_sources"
    __table_args__ = (
        Index(
            "ux_place_sources_external",
            "source_type",
            "external_id",
            unique=True,
            sqlite_where=text("external_id IS NOT NULL AND external_id != ''"),
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    place_id: Mapped[int] = mapped_column(ForeignKey("places.id"), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(200))
    source_url: Mapped[str | None] = mapped_column(String(500))
    fetched_at: Mapped[str | None] = mapped_column(String(40))
    license: Mapped[str | None] = mapped_column(String(80))
    raw_data: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False, default=now_iso)
    updated_at: Mapped[str] = mapped_column(String(40), nullable=False, default=now_iso)

    place: Mapped[Place] = relationship(back_populates="sources")
    values: Mapped[list["PlaceSourceValue"]] = relationship(
        back_populates="place_source",
        lazy="selectin",
        cascade="all, delete-orphan",
    )


class PlaceSourceValue(Base):
    __tablename__ = "place_source_values"
    __table_args__ = (UniqueConstraint("place_source_id", "field_name", name="ux_place_source_values_field"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    place_source_id: Mapped[int] = mapped_column(ForeignKey("place_sources.id", ondelete="CASCADE"), nullable=False)
    field_name: Mapped[str] = mapped_column(String(80), nullable=False)
    value_json: Mapped[str] = mapped_column(Text, nullable=False)
    fetched_at: Mapped[str] = mapped_column(String(40), nullable=False)

    place_source: Mapped[PlaceSource] = relationship(back_populates="values")


class PlaceFieldOverride(Base):
    __tablename__ = "place_field_overrides"

    place_id: Mapped[int] = mapped_column(ForeignKey("places.id"), primary_key=True)
    field_name: Mapped[str] = mapped_column(String(80), primary_key=True)
    value_json: Mapped[str] = mapped_column(Text, nullable=False)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False, default=now_iso)
    updated_at: Mapped[str] = mapped_column(String(40), nullable=False, default=now_iso)

    place: Mapped[Place] = relationship(back_populates="field_overrides")


class PlacePhoto(Base):
    __tablename__ = "place_photos"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    place_id: Mapped[int] = mapped_column(ForeignKey("places.id"), nullable=False, index=True)
    source: Mapped[str] = mapped_column(String(40), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(500))
    original_url: Mapped[str | None] = mapped_column(String(500))
    thumbnail_url: Mapped[str | None] = mapped_column(String(500))
    author: Mapped[str | None] = mapped_column(String(300))
    license: Mapped[str | None] = mapped_column(String(80))
    license_url: Mapped[str | None] = mapped_column(String(500))
    attribution: Mapped[str | None] = mapped_column(Text)
    is_primary: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False, default=now_iso)

    place: Mapped[Place] = relationship(back_populates="photos")


class ImportRun(Base):
    __tablename__ = "import_runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    started_at: Mapped[str] = mapped_column(String(40), nullable=False, default=now_iso)
    finished_at: Mapped[str | None] = mapped_column(String(40))
    records_received: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_unchanged: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_review: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_failed: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    records_ignored: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    backup_path: Mapped[str | None] = mapped_column(Text)
    log: Mapped[str | None] = mapped_column(Text)

    reviews: Mapped[list["ImportReview"]] = relationship(
        back_populates="import_run",
        lazy="selectin",
        cascade="all, delete-orphan",
    )
    field_changes: Mapped[list["ImportFieldChange"]] = relationship(
        back_populates="import_run",
        lazy="selectin",
        cascade="all, delete-orphan",
    )


class ImportReview(Base):
    __tablename__ = "import_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    import_run_id: Mapped[int] = mapped_column(ForeignKey("import_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(200), index=True)
    candidate_place_id: Mapped[int | None] = mapped_column(ForeignKey("places.id"))
    match_score: Mapped[float | None] = mapped_column(Float)
    match_reason: Mapped[str | None] = mapped_column(Text)
    raw_data: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open", index=True)
    resolution: Mapped[str | None] = mapped_column(Text)
    resolved_at: Mapped[str | None] = mapped_column(String(40))

    import_run: Mapped[ImportRun] = relationship(back_populates="reviews")
    candidate_place: Mapped[Place | None] = relationship(foreign_keys=[candidate_place_id])
    candidates: Mapped[list["ImportReviewCandidate"]] = relationship(
        back_populates="import_review",
        lazy="selectin",
        cascade="all, delete-orphan",
        order_by="ImportReviewCandidate.score.desc()",
    )


class ImportReviewCandidate(Base):
    __tablename__ = "import_review_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    import_review_id: Mapped[int] = mapped_column(
        ForeignKey("import_reviews.id", ondelete="CASCADE"), nullable=False, index=True
    )
    place_id: Mapped[int] = mapped_column(ForeignKey("places.id"), nullable=False)
    score: Mapped[float | None] = mapped_column(Float)
    reason: Mapped[str | None] = mapped_column(Text)

    import_review: Mapped[ImportReview] = relationship(back_populates="candidates")
    place: Mapped[Place] = relationship()


class ImportFieldChange(Base):
    __tablename__ = "import_field_changes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    import_run_id: Mapped[int] = mapped_column(ForeignKey("import_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    place_id: Mapped[int] = mapped_column(ForeignKey("places.id"), nullable=False, index=True)
    field_name: Mapped[str] = mapped_column(String(80), nullable=False)
    old_source_value: Mapped[str | None] = mapped_column(Text)
    new_source_value: Mapped[str | None] = mapped_column(Text)
    master_value: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="open")
    resolved_at: Mapped[str | None] = mapped_column(String(40))

    import_run: Mapped[ImportRun] = relationship(back_populates="field_changes")
    place: Mapped[Place] = relationship()


class Visit(Base):
    __tablename__ = "visits"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, default=new_public_id)
    place_id: Mapped[int | None] = mapped_column(ForeignKey("places.id"), nullable=True, index=True)
    place_public_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    visited_at: Mapped[str | None] = mapped_column(String(10))
    rating: Mapped[int | None] = mapped_column(Integer)
    people_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    note: Mapped[str | None] = mapped_column(Text)
    trip_public_id: Mapped[str | None] = mapped_column(String(36), index=True)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False, default=now_iso)
    updated_at: Mapped[str] = mapped_column(String(40), nullable=False, default=now_iso)
    deleted_at: Mapped[str | None] = mapped_column(String(40), index=True)

    place: Mapped[Place | None] = relationship(back_populates="visits")

    @property
    def people(self) -> list[str]:
        try:
            data = json.loads(self.people_json or "[]")
        except json.JSONDecodeError:
            return []
        return [str(item) for item in data] if isinstance(data, list) else []

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class PlaceJournalState(Base):
    __tablename__ = "place_journal_states"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    place_public_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    place_id: Mapped[int | None] = mapped_column(ForeignKey("places.id"), nullable=True, index=True)
    want_to_visit: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    favorite: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    personal_note: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[str] = mapped_column(String(40), nullable=False, default=now_iso)
    deleted_at: Mapped[str | None] = mapped_column(String(40))

    place: Mapped[Place | None] = relationship(back_populates="journal_state")

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


class Trip(Base):
    __tablename__ = "trips"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    public_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False, default=new_public_id)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    planned_on: Mapped[str | None] = mapped_column(String(10))
    origin_latitude: Mapped[float | None] = mapped_column(Float)
    origin_longitude: Mapped[float | None] = mapped_column(Float)
    origin_label: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned")
    created_at: Mapped[str] = mapped_column(String(40), nullable=False, default=now_iso)
    updated_at: Mapped[str] = mapped_column(String(40), nullable=False, default=now_iso)
    deleted_at: Mapped[str | None] = mapped_column(String(40), index=True)

    stops: Mapped[list["TripStop"]] = relationship(
        back_populates="trip",
        cascade="all, delete-orphan",
        order_by="TripStop.sort_order",
        lazy="selectin",
    )

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    @property
    def origin(self) -> dict[str, float | str] | None:
        if self.origin_latitude is None or self.origin_longitude is None:
            return None
        return {
            "latitude": self.origin_latitude,
            "longitude": self.origin_longitude,
            "label": self.origin_label or "",
        }


class TripStop(Base):
    __tablename__ = "trip_stops"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    trip_id: Mapped[int] = mapped_column(ForeignKey("trips.id", ondelete="CASCADE"), nullable=False, index=True)
    place_id: Mapped[int | None] = mapped_column(ForeignKey("places.id"), nullable=True, index=True)
    place_public_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    note: Mapped[str | None] = mapped_column(Text)

    trip: Mapped[Trip] = relationship(back_populates="stops")
    place: Mapped[Place | None] = relationship()


class DiaryImportIssue(Base):
    __tablename__ = "diary_import_issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    place_public_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    visit_public_id: Mapped[str | None] = mapped_column(String(36))
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[str] = mapped_column(String(40), nullable=False, default=now_iso)
    resolved_at: Mapped[str | None] = mapped_column(String(40), index=True)


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
