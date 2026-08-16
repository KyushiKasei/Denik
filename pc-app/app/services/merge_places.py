"""Sloučení dvou existujících Place. Vítěz si nechá public_id, poražený se archivuje."""

from __future__ import annotations

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import (
    ImportFieldChange,
    ImportReview,
    ImportReviewCandidate,
    Place,
    PlaceFieldOverride,
    PlaceJournalState,
    PlacePhoto,
    PlaceSource,
    TripStop,
    Visit,
    now_iso,
)
from app.services.diary_io import incoming_is_newer
from app.logging_setup import get_logger
from app.services.matching import normalize_name
from app.services.places import dump_alternative_names

_log = get_logger()

_EMPTY_MASTER_FIELDS = (
    "short_name",
    "short_description",
    "latitude",
    "longitude",
    "address",
    "municipality",
    "municipality_code",
    "district",
    "district_code",
    "region",
    "region_code",
    "official_website",
    "wikipedia_url",
    "opening_hours_url",
    "ticket_url",
    "heritage_status",
)


class MergeError(ValueError):
    pass


def find_merge_candidates(session: Session, place: Place, q: str = "") -> list[Place]:
    """Aktivní místa k sloučení: hledání, jinak stejný normalizovaný název."""
    rows = list(
        session.scalars(
            select(Place)
            .where(Place.id != place.id, Place.archived_at.is_(None))
            .order_by(Place.name.asc())
        ).all()
    )
    term = q.strip().lower()
    if term:
        return [
            row
            for row in rows
            if term in row.name.lower()
            or (row.municipality or "").lower().find(term) >= 0
            or term in row.public_id.lower()
            or any(term in alt.lower() for alt in row.alt_names)
        ][:50]
    needle = normalize_name(place.name)
    if not needle:
        return rows[:30]
    same = [row for row in rows if normalize_name(row.name) == needle or needle in {normalize_name(a) for a in row.alt_names}]
    return same or rows[:30]


def merge_places(session: Session, winner: Place, loser: Place) -> Place:
    if winner.id == loser.id:
        raise MergeError("Nelze sloučit místo samo se sebou.")
    if winner.archived_at is not None:
        raise MergeError("Vítězné místo je v archivu.")
    if loser.merged_into_public_id:
        raise MergeError("Toto místo už bylo sloučeno do jiného.")

    winner_id = winner.public_id
    _move_sources(session, winner, loser)
    _union_types(winner, loser)
    _union_alt_names(winner, loser)
    _fill_empty_fields(winner, loser)
    _move_photos(session, winner, loser)
    _move_overrides(session, winner, loser)
    _repoint_reviews(session, winner, loser)
    _repoint_field_changes(session, winner, loser)
    _repoint_diary_tables(session, winner, loser)

    loser.archived_at = now_iso()
    loser.merged_into_public_id = winner.public_id
    loser.updated_at = loser.archived_at
    winner.updated_at = now_iso()
    if winner.public_id != winner_id:
        raise MergeError("Place.public_id is immutable and must never be changed")

    session.commit()
    session.refresh(winner)
    _log.info(
        "places merged winner=%s loser=%s merged_into_public_id=%s",
        winner.public_id,
        loser.public_id,
        winner.public_id,
    )
    return winner


def _move_sources(session: Session, winner: Place, loser: Place) -> None:
    winner_keys = {(s.source_type, s.external_id) for s in winner.sources if s.external_id}
    for source in list(loser.sources):
        key = (source.source_type, source.external_id)
        if source.external_id and key in winner_keys:
            session.delete(source)
            continue
        source.place_id = winner.id
        source.place = winner


def _union_types(winner: Place, loser: Place) -> None:
    seen = {item.code for item in winner.types}
    extra = [item for item in loser.types if item.code not in seen]
    if extra:
        winner.types = [*winner.types, *extra]


def _union_alt_names(winner: Place, loser: Place) -> None:
    seen = set(winner.alt_names)
    merged = list(winner.alt_names)
    for name in [loser.name, *loser.alt_names]:
        text = (name or "").strip()
        if not text or text == winner.name or text in seen:
            continue
        seen.add(text)
        merged.append(text)
    winner.alternative_names = dump_alternative_names(merged)


def _fill_empty_fields(winner: Place, loser: Place) -> None:
    for field_name in _EMPTY_MASTER_FIELDS:
        current = getattr(winner, field_name)
        incoming = getattr(loser, field_name)
        if incoming in (None, "") or current not in (None, ""):
            continue
        setattr(winner, field_name, incoming)
    if (winner.condition or "UNKNOWN") == "UNKNOWN" and loser.condition and loser.condition != "UNKNOWN":
        winner.condition = loser.condition
    if (winner.visitability or "UNKNOWN") == "UNKNOWN" and loser.visitability and loser.visitability != "UNKNOWN":
        winner.visitability = loser.visitability
    if not winner.unesco and loser.unesco:
        winner.unesco = loser.unesco


def _move_photos(session: Session, winner: Place, loser: Place) -> None:
    winner_urls = {p.original_url for p in winner.photos if p.original_url}
    has_primary = any(p.is_primary for p in winner.photos)
    for photo in list(loser.photos):
        if photo.original_url and photo.original_url in winner_urls:
            session.delete(photo)
            continue
        if has_primary:
            photo.is_primary = 0
        photo.place_id = winner.id
        photo.place = winner


def _move_overrides(session: Session, winner: Place, loser: Place) -> None:
    winner_fields = {row.field_name for row in winner.field_overrides}
    for row in list(loser.field_overrides):
        if row.field_name in winner_fields:
            session.delete(row)
            continue
        session.delete(row)
        session.flush()
        session.add(
            PlaceFieldOverride(
                place_id=winner.id,
                field_name=row.field_name,
                value_json=row.value_json,
                note=row.note,
                created_at=row.created_at,
                updated_at=now_iso(),
            )
        )


def _repoint_reviews(session: Session, winner: Place, loser: Place) -> None:
    for review in session.scalars(select(ImportReview).where(ImportReview.candidate_place_id == loser.id)).all():
        review.candidate_place_id = winner.id
    for cand in session.scalars(select(ImportReviewCandidate).where(ImportReviewCandidate.place_id == loser.id)).all():
        exists = session.scalar(
            select(ImportReviewCandidate.id).where(
                ImportReviewCandidate.import_review_id == cand.import_review_id,
                ImportReviewCandidate.place_id == winner.id,
            )
        )
        if exists:
            session.delete(cand)
        else:
            cand.place_id = winner.id


def _repoint_field_changes(session: Session, winner: Place, loser: Place) -> None:
    for change in session.scalars(select(ImportFieldChange).where(ImportFieldChange.place_id == loser.id)).all():
        change.place_id = winner.id


def _repoint_diary_tables(session: Session, winner: Place, loser: Place) -> None:
    """Převést návštěvy a stavy na vítěze. public_id návštěvy se nemění."""
    visits = list(
        session.scalars(
            select(Visit).where(
                or_(Visit.place_id == loser.id, Visit.place_public_id == loser.public_id)
            )
        ).all()
    )
    for visit in visits:
        visit.place_id = winner.id
        visit.place_public_id = winner.public_id

    stops = list(
        session.scalars(
            select(TripStop).where(
                or_(TripStop.place_id == loser.id, TripStop.place_public_id == loser.public_id)
            )
        ).all()
    )
    for stop in stops:
        stop.place_id = winner.id
        stop.place_public_id = winner.public_id

    loser_state = session.scalar(
        select(PlaceJournalState).where(PlaceJournalState.place_public_id == loser.public_id)
    )
    winner_state = session.scalar(
        select(PlaceJournalState).where(PlaceJournalState.place_public_id == winner.public_id)
    )
    if loser_state is None:
        if winner_state is not None:
            winner_state.place_id = winner.id
        return
    if winner_state is None:
        loser_state.place_id = winner.id
        loser_state.place_public_id = winner.public_id
        return

    apply, _tied = incoming_is_newer(loser_state.updated_at, winner_state.updated_at)
    if apply:
        winner_state.want_to_visit = loser_state.want_to_visit
        winner_state.favorite = loser_state.favorite
        winner_state.personal_note = loser_state.personal_note
        winner_state.updated_at = loser_state.updated_at
        winner_state.deleted_at = loser_state.deleted_at
    winner_state.place_id = winner.id
    session.delete(loser_state)
