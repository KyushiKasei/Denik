"""Rodinné sloučení deníku: stejné místo a den = jedno razítko."""

from __future__ import annotations

import json
import shutil
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PlaceJournalState, Visit, now_iso
from app.services.visit_photos import (
    MAX_PHOTOS_PER_VISIT,
    is_visit_id,
    list_visit_photos,
    visit_photo_dir,
)


def merge_people(left: list[str], right: list[str]) -> list[str]:
    seen: set[str] = set()
    names: list[str] = []
    for name in [*left, *right]:
        trimmed = name.strip()
        if not trimmed:
            continue
        key = trimmed.casefold()
        if key in seen:
            continue
        seen.add(key)
        names.append(trimmed)
    return names


def merge_notes(left: str | None, right: str | None) -> str | None:
    a = (left or "").strip()
    b = (right or "").strip()
    if a and b and a.casefold() != b.casefold():
        return f"{a} · {b}"
    return a or b or None


def visit_richness(visit: Visit) -> tuple[int, str]:
    score = 0
    if visit.note and visit.note.strip():
        score += 2
    if visit.rating:
        score += 1
    score += min(3, len(visit.people))
    photos = list_visit_photos(visit.public_id) if is_visit_id(visit.public_id) else []
    score += min(3, len(photos))
    return (score, visit.created_at)


def _family_rank(visit: Visit) -> tuple:
    """Stejné pořadí jako PWA: vyšší skóre, novější created_at, menší id."""
    score, created = visit_richness(visit)
    return (-score, tuple(-ord(c) for c in created), visit.public_id)


def _move_photos(loser_id: str, winner_id: str) -> None:
    if loser_id == winner_id or not is_visit_id(loser_id) or not is_visit_id(winner_id):
        return
    source = list_visit_photos(loser_id)
    if not source:
        return
    dest = visit_photo_dir(winner_id)
    folder = source[0].parent
    dest_count = len(list_visit_photos(winner_id))
    for path in source:
        target = dest / path.name
        if target.exists() or dest_count >= MAX_PHOTOS_PER_VISIT:
            path.unlink(missing_ok=True)
            continue
        shutil.move(path, target)
        dest_count += 1
    try:
        folder.rmdir()
    except OSError:
        pass


def collapse_family_visits(session: Session) -> int:
    """Stejné place_id + visited_at (s datem) sloučí do jedné živé návštěvy."""
    # Session má autoflush=False — bez flush SELECT neuvidí návštěvy právě přidané importem.
    session.flush()
    live = list(session.scalars(select(Visit).where(Visit.deleted_at.is_(None))).all())
    groups: dict[tuple[str, str], list[Visit]] = defaultdict(list)
    for visit in live:
        day = (visit.visited_at or "").strip()
        if not day:
            continue
        groups[(visit.place_public_id, day)].append(visit)
    collapsed = 0
    stamp = now_iso()
    for rows in groups.values():
        if len(rows) < 2:
            continue
        ranked = sorted(rows, key=_family_rank)
        winner = ranked[0]
        for loser in ranked[1:]:
            winner.people_json = json.dumps(merge_people(winner.people, loser.people), ensure_ascii=False)
            winner.note = merge_notes(winner.note, loser.note)
            if loser.rating is not None and (winner.rating is None or loser.rating > winner.rating):
                winner.rating = loser.rating
            if loser.trip_public_id and not winner.trip_public_id:
                winner.trip_public_id = loser.trip_public_id
            _move_photos(loser.public_id, winner.public_id)
            loser.deleted_at = stamp
            loser.updated_at = stamp
            collapsed += 1
        winner.updated_at = stamp
    return collapsed


def family_or_state(local: PlaceJournalState, incoming: dict) -> None:
    local.want_to_visit = 1 if local.want_to_visit or incoming.get("want_to_visit") else 0
    local.favorite = 1 if local.favorite or incoming.get("favorite") else 0
    local.personal_note = merge_notes(local.personal_note, incoming.get("personal_note"))
    local.updated_at = now_iso()
    local.deleted_at = None
