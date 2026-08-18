"""Jednorázová čistota katalogu (fáze 11): stav zřícenin a známé špatné štítky."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Place, PlacePlaceType, PlaceSource, PlaceType, now_iso
from app.services.overrides import apply_value_to_place, has_override, snapshot_place, upsert_override
from app.services.places import mark_ruins_free_access
from app.services.values import values_equal

CLEANUP_NOTE = "Čistota katalogu — fáze 11"

KARLSTEJN_CASTLE_ID = "01a001c5-4afb-779f-82a6-ded66735a1f7"
VYSEHRAD_ID = "01a001eb-ce5e-74bd-89dc-78a80ecee930"
BARRANDOV_ID = "01a00c2e-9a14-7214-a539-5c6ca344431b"
TEXTILKA_ID = "01a01157-907a-75b2-b5d8-07ff9d0d6810"
UHERCICE_ID = "01a0049f-0027-7336-b045-4fd315da442e"
UNCLEAR_KARLSTEIN_QID = "Q-unclear-karlstein"


@dataclass
class CleanupResult:
    dry_run: bool
    condition_backfill: int = 0
    skipped_override: int = 0
    curated: int = 0
    detached_sources: int = 0
    missing: list[str] = field(default_factory=list)
    already: int = 0
    backup_path: Path | None = None


def _active_by_public_id(session: Session, public_id: str) -> Place | None:
    return session.scalar(
        select(Place).where(Place.public_id == public_id, Place.archived_at.is_(None))
    )


def _apply_fields(
    session: Session,
    place: Place,
    fields: dict[str, object],
    *,
    dry_run: bool,
) -> bool:
    before = snapshot_place(place)
    changed = False
    for field_name, value in fields.items():
        if values_equal(before.get(field_name), value):
            if not dry_run and not has_override(session, place.id, field_name):
                upsert_override(session, place, field_name, value, note=CLEANUP_NOTE)
            continue
        changed = True
        if dry_run:
            continue
        apply_value_to_place(place, field_name, value, session)
        upsert_override(session, place, field_name, value, note=CLEANUP_NOTE)
        place.updated_at = now_iso()
    return changed


def _detach_unclear_karlstein(session: Session, place: Place, *, dry_run: bool) -> int:
    row = session.scalar(
        select(PlaceSource).where(
            PlaceSource.place_id == place.id,
            PlaceSource.source_type == "wikidata",
            PlaceSource.external_id == UNCLEAR_KARLSTEIN_QID,
        )
    )
    if row is None:
        return 0
    if not dry_run:
        session.delete(row)
        place.updated_at = now_iso()
    return 1


def backfill_ruin_condition(session: Session, *, dry_run: bool = False) -> tuple[int, int]:
    ruin_type = (
        select(PlacePlaceType.place_id)
        .join(PlaceType, PlaceType.id == PlacePlaceType.place_type_id)
        .where(PlaceType.code == "RUIN")
    )
    places = list(
        session.scalars(
            select(Place).where(
                Place.archived_at.is_(None),
                Place.condition == "UNKNOWN",
                Place.id.in_(ruin_type),
            )
        ).all()
    )
    updated = 0
    skipped = 0
    now = now_iso()
    for place in places:
        if has_override(session, place.id, "condition"):
            skipped += 1
            continue
        updated += 1
        if dry_run:
            continue
        place.condition = "RUIN"
        place.updated_at = now
    return updated, skipped


def apply_curated_fixes(session: Session, *, dry_run: bool = False) -> tuple[int, int, list[str], int]:
    specs: list[tuple[str, dict[str, object]]] = [
        (KARLSTEJN_CASTLE_ID, {"short_description": None}),
        (VYSEHRAD_ID, {"types": ["CASTLE"], "condition": "PRESERVED"}),
        (BARRANDOV_ID, {"types": ["OTHER"]}),
        (TEXTILKA_ID, {"types": ["OTHER"]}),
        (UHERCICE_ID, {"municipality": "Uherčice", "district": "Znojmo"}),
    ]
    curated = 0
    detached = 0
    missing: list[str] = []
    already = 0
    for public_id, fields in specs:
        place = _active_by_public_id(session, public_id)
        if place is None:
            missing.append(public_id)
            continue
        changed = _apply_fields(session, place, fields, dry_run=dry_run)
        extra = 0
        if public_id == KARLSTEJN_CASTLE_ID:
            extra = _detach_unclear_karlstein(session, place, dry_run=dry_run)
            detached += extra
        if changed or extra:
            curated += 1
        else:
            already += 1
    return curated, detached, missing, already


def cleanup_catalog(session: Session, *, dry_run: bool = False) -> CleanupResult:
    result = CleanupResult(dry_run=dry_run)
    result.condition_backfill, result.skipped_override = backfill_ruin_condition(
        session, dry_run=dry_run
    )
    curated, detached, missing, already = apply_curated_fixes(session, dry_run=dry_run)
    result.curated = curated
    result.detached_sources = detached
    result.missing = missing
    result.already = already
    if not dry_run:
        mark_ruins_free_access(session)
        session.commit()
    return result
