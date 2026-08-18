"""Import a export diary.json. Idempotentní sloučení podle PLAN.md kapitoly 10.

Nikdy nevytváří Place, nemění master sloupce Place, nevytváří druhou návštěvu se stejným id.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from urllib.parse import urlencode

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, joinedload

from app.config import get_default_diary_path
from app.db.models import (
    AppMeta,
    DiaryImportIssue,
    Place,
    PlaceJournalState,
    Trip,
    TripStop,
    Visit,
    now_iso,
)
from app.ids import new_public_id
from app.logging_setup import get_logger
from app.services.backup import backup_before_import
from app.services.diary_schema import SCHEMA_VERSION, validate_diary

_log = get_logger()

META_DIARY_IMPORT_AT = "last_diary_import_at"
META_DIARY_EXPORT_AT = "last_diary_export_at"

ISSUE_UNKNOWN_PLACE = "unknown_place"


@dataclass
class DiaryImportResult:
    visits_inserted: int = 0
    visits_updated: int = 0
    visits_unchanged: int = 0
    states_inserted: int = 0
    states_updated: int = 0
    states_unchanged: int = 0
    trips_inserted: int = 0
    trips_updated: int = 0
    trips_unchanged: int = 0
    unknown_place_ids: list[str] = field(default_factory=list)
    backup_path: Path | None = None
    warnings: list[str] = field(default_factory=list)
    family_collapsed: int = 0


@dataclass(frozen=True)
class DiaryExportResult:
    path: Path
    visit_count: int
    state_count: int
    diary: dict[str, Any]


def parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.astimezone()
    return parsed


def incoming_is_newer(incoming_at: str | None, local_at: str | None) -> tuple[bool, bool]:
    """Vrátí (použít příchozí, shodný čas).

    Novější updated_at vyhraje. Při shodném čase vyhraje příchozí (volající zapíše varování,
    pokud se pole liší). Starší příchozí se neaplikuje.
    """
    incoming_dt = parse_timestamp(incoming_at)
    local_dt = parse_timestamp(local_at)
    if incoming_dt is None and local_dt is None:
        return True, True
    if incoming_dt is None:
        return False, False
    if local_dt is None:
        return True, False
    if incoming_dt > local_dt:
        return True, False
    if incoming_dt < local_dt:
        return False, False
    return True, True


def _get_meta(session: Session, key: str) -> str | None:
    row = session.get(AppMeta, key)
    return row.value if row is not None else None


def _set_meta(session: Session, key: str, value: str) -> None:
    row = session.get(AppMeta, key)
    if row is None:
        session.add(AppMeta(key=key, value=value))
    else:
        row.value = value


def _people_json(people: Any) -> str:
    if not isinstance(people, list):
        return "[]"
    names = [str(item).strip() for item in people if str(item).strip()]
    return json.dumps(names, ensure_ascii=False)


def _place_by_public_id(session: Session, public_id: str) -> Place | None:
    return session.scalar(select(Place).where(Place.public_id == public_id))


def _open_issue(session: Session, place_public_id: str, visit_public_id: str | None) -> None:
    existing = session.scalar(
        select(DiaryImportIssue).where(
            DiaryImportIssue.place_public_id == place_public_id,
            DiaryImportIssue.kind == ISSUE_UNKNOWN_PLACE,
            DiaryImportIssue.resolved_at.is_(None),
        )
    )
    if existing is not None:
        if visit_public_id and not existing.visit_public_id:
            existing.visit_public_id = visit_public_id
        return
    session.add(
        DiaryImportIssue(
            place_public_id=place_public_id,
            visit_public_id=visit_public_id,
            kind=ISSUE_UNKNOWN_PLACE,
            created_at=now_iso(),
        )
    )


def relink_unknown_diary_rows(session: Session) -> int:
    """Pokud Place mezitím existuje, navázat FK a uzavřít issue. Place se nevytváří."""
    resolved = 0
    open_issues = list(
        session.scalars(
            select(DiaryImportIssue).where(DiaryImportIssue.resolved_at.is_(None))
        ).all()
    )
    for issue in open_issues:
        place = _place_by_public_id(session, issue.place_public_id)
        if place is None:
            continue
        for visit in session.scalars(
            select(Visit).where(Visit.place_public_id == issue.place_public_id, Visit.place_id.is_(None))
        ).all():
            visit.place_id = place.id
        state = session.scalar(
            select(PlaceJournalState).where(PlaceJournalState.place_public_id == issue.place_public_id)
        )
        if state is not None and state.place_id is None:
            state.place_id = place.id
        for stop in session.scalars(
            select(TripStop).where(TripStop.place_public_id == issue.place_public_id, TripStop.place_id.is_(None))
        ).all():
            stop.place_id = place.id
        issue.resolved_at = now_iso()
        resolved += 1
    return resolved


def _visit_payload_equal(visit: Visit, item: dict[str, Any]) -> bool:
    return (
        visit.place_public_id == item.get("place_id")
        and visit.visited_at == item.get("visited_at")
        and visit.rating == item.get("rating")
        and visit.people == (item.get("people") or [])
        and (visit.note or None) == (item.get("note") or None)
        and (visit.trip_public_id or None) == (item.get("trip_id") or None)
        and (visit.deleted_at or None) == (item.get("deleted_at") or None)
        and visit.created_at == item.get("created_at")
        and visit.updated_at == item.get("updated_at")
    )


def _apply_visit_fields(visit: Visit, item: dict[str, Any], place: Place | None) -> None:
    visit.place_public_id = str(item["place_id"])
    visit.place_id = place.id if place is not None else None
    visit.visited_at = item.get("visited_at")
    visit.rating = item.get("rating")
    visit.people_json = _people_json(item.get("people"))
    visit.note = item.get("note")
    trip_id = item.get("trip_id")
    visit.trip_public_id = str(trip_id) if trip_id else None
    visit.created_at = str(item["created_at"])
    visit.updated_at = str(item["updated_at"])
    visit.deleted_at = item.get("deleted_at")


def _merge_visit(session: Session, item: dict[str, Any], result: DiaryImportResult) -> None:
    public_id = str(item["id"])
    place_public_id = str(item["place_id"])
    place = _place_by_public_id(session, place_public_id)
    if place is None:
        if place_public_id not in result.unknown_place_ids:
            result.unknown_place_ids.append(place_public_id)
        _open_issue(session, place_public_id, public_id)

    local = session.scalar(select(Visit).where(Visit.public_id == public_id))
    if local is None:
        visit = Visit(public_id=public_id)
        _apply_visit_fields(visit, item, place)
        session.add(visit)
        result.visits_inserted += 1
        return

    apply, tied = incoming_is_newer(item.get("updated_at"), local.updated_at)
    if not apply:
        result.visits_unchanged += 1
        return
    if tied and _visit_payload_equal(local, item):
        if place is not None and local.place_id is None:
            local.place_id = place.id
        result.visits_unchanged += 1
        return
    if tied:
        warning = f"Návštěva {public_id}: stejný updated_at, použita příchozí hodnota."
        result.warnings.append(warning)
        _log.warning("diary visit tie-break id=%s incoming wins", public_id)

    _apply_visit_fields(local, item, place)
    result.visits_updated += 1


def _state_payload_equal(state: PlaceJournalState, item: dict[str, Any]) -> bool:
    return (
        bool(state.want_to_visit) == bool(item.get("want_to_visit"))
        and bool(state.favorite) == bool(item.get("favorite"))
        and (state.personal_note or None) == (item.get("personal_note") or None)
        and (state.deleted_at or None) == (item.get("deleted_at") or None)
        and state.updated_at == item.get("updated_at")
    )


def _apply_state_fields(state: PlaceJournalState, item: dict[str, Any], place: Place | None) -> None:
    state.place_public_id = str(item["place_id"])
    state.place_id = place.id if place is not None else None
    state.want_to_visit = 1 if item.get("want_to_visit") else 0
    state.favorite = 1 if item.get("favorite") else 0
    state.personal_note = item.get("personal_note")
    state.updated_at = str(item["updated_at"])
    state.deleted_at = item.get("deleted_at")


def _merge_state(session: Session, item: dict[str, Any], result: DiaryImportResult) -> None:
    place_public_id = str(item["place_id"])
    place = _place_by_public_id(session, place_public_id)
    if place is None:
        if place_public_id not in result.unknown_place_ids:
            result.unknown_place_ids.append(place_public_id)
        _open_issue(session, place_public_id, None)

    local = session.scalar(
        select(PlaceJournalState).where(PlaceJournalState.place_public_id == place_public_id)
    )
    if local is None:
        state = PlaceJournalState(place_public_id=place_public_id)
        _apply_state_fields(state, item, place)
        session.add(state)
        result.states_inserted += 1
        return

    apply, tied = incoming_is_newer(item.get("updated_at"), local.updated_at)
    if not apply:
        result.states_unchanged += 1
        return
    if tied and _state_payload_equal(local, item):
        if place is not None and local.place_id is None:
            local.place_id = place.id
        result.states_unchanged += 1
        return
    if tied:
        warning = f"Stav místa {place_public_id}: stejný updated_at, použita příchozí hodnota."
        result.warnings.append(warning)
        _log.warning("diary place_state tie-break place_id=%s incoming wins", place_public_id)

    _apply_state_fields(local, item, place)
    result.states_updated += 1


def _merge_state_family(session: Session, item: dict[str, Any], result: DiaryImportResult) -> None:
    """Rodina: chci/oblíbené se sčítají, poznámky se spojí. Jinak stejné ID pravidlo."""
    from app.services.family_merge import family_or_state

    place_public_id = str(item["place_id"])
    place = _place_by_public_id(session, place_public_id)
    if place is None:
        if place_public_id not in result.unknown_place_ids:
            result.unknown_place_ids.append(place_public_id)
        _open_issue(session, place_public_id, None)

    local = session.scalar(
        select(PlaceJournalState).where(PlaceJournalState.place_public_id == place_public_id)
    )
    if local is None:
        state = PlaceJournalState(place_public_id=place_public_id)
        _apply_state_fields(state, item, place)
        session.add(state)
        result.states_inserted += 1
        return
    if local.deleted_at and not item.get("deleted_at"):
        _apply_state_fields(local, item, place)
        result.states_updated += 1
        return
    family_or_state(local, item)
    if place is not None:
        local.place_id = place.id
    result.states_updated += 1


def _origin_tuple(item: dict[str, Any]) -> tuple[float | None, float | None, str | None]:
    origin = item.get("origin")
    if not isinstance(origin, dict):
        return None, None, None
    lat = origin.get("latitude")
    lon = origin.get("longitude")
    label = str(origin.get("label") or "").strip() or None
    return (
        float(lat) if isinstance(lat, (int, float)) else None,
        float(lon) if isinstance(lon, (int, float)) else None,
        label,
    )


def _stops_payload(item: dict[str, Any]) -> list[tuple[str, int, str | None]]:
    rows: list[tuple[str, int, str | None]] = []
    for stop in item.get("stops") or []:
        if not isinstance(stop, dict):
            continue
        place_id = str(stop.get("place_id") or "")
        try:
            order = int(stop.get("sort_order") or 0)
        except (TypeError, ValueError):
            order = 0
        note = str(stop.get("note") or "").strip() or None
        if place_id:
            rows.append((place_id, order, note))
    rows.sort(key=lambda row: row[1])
    return rows


def _trip_payload_equal(trip: Trip, item: dict[str, Any]) -> bool:
    lat, lon, label = _origin_tuple(item)
    local_stops = [(stop.place_public_id, stop.sort_order, stop.note or None) for stop in trip.stops]
    return (
        trip.name == item.get("name")
        and (trip.planned_on or None) == (item.get("planned_on") or None)
        and trip.origin_latitude == lat
        and trip.origin_longitude == lon
        and (trip.origin_label or None) == label
        and (trip.notes or None) == (item.get("notes") or None)
        and (trip.status or "planned") == (item.get("status") or "planned")
        and (trip.deleted_at or None) == (item.get("deleted_at") or None)
        and trip.created_at == item.get("created_at")
        and trip.updated_at == item.get("updated_at")
        and local_stops == _stops_payload(item)
    )


def _replace_trip_stops(session: Session, trip: Trip, item: dict[str, Any], result: DiaryImportResult) -> None:
    trip.stops.clear()
    session.flush()
    for place_public_id, order, note in _stops_payload(item):
        place = _place_by_public_id(session, place_public_id)
        if place is None:
            if place_public_id not in result.unknown_place_ids:
                result.unknown_place_ids.append(place_public_id)
            _open_issue(session, place_public_id, None)
        trip.stops.append(
            TripStop(
                place_public_id=place_public_id,
                place_id=place.id if place is not None else None,
                sort_order=order,
                note=note,
            )
        )


def _apply_trip_fields(session: Session, trip: Trip, item: dict[str, Any], result: DiaryImportResult) -> None:
    lat, lon, label = _origin_tuple(item)
    trip.name = str(item.get("name") or "Výlet")
    trip.planned_on = item.get("planned_on")
    trip.origin_latitude = lat
    trip.origin_longitude = lon
    trip.origin_label = label
    trip.notes = item.get("notes")
    status = str(item.get("status") or "planned").strip()
    trip.status = status if status in {"planned", "partial", "done"} else "planned"
    trip.created_at = str(item["created_at"])
    trip.updated_at = str(item["updated_at"])
    trip.deleted_at = item.get("deleted_at")
    _replace_trip_stops(session, trip, item, result)


def _merge_trip(session: Session, item: dict[str, Any], result: DiaryImportResult) -> None:
    public_id = str(item["id"])
    local = session.scalar(select(Trip).where(Trip.public_id == public_id))
    if local is None:
        trip = Trip(public_id=public_id, name=str(item.get("name") or "Výlet"))
        session.add(trip)
        session.flush()
        _apply_trip_fields(session, trip, item, result)
        result.trips_inserted += 1
        return

    apply, tied = incoming_is_newer(item.get("updated_at"), local.updated_at)
    if not apply:
        result.trips_unchanged += 1
        return
    if tied and _trip_payload_equal(local, item):
        result.trips_unchanged += 1
        return
    if tied:
        warning = f"Výlet {public_id}: stejný updated_at, použita příchozí hodnota."
        result.warnings.append(warning)
        _log.warning("diary trip tie-break id=%s incoming wins", public_id)

    _apply_trip_fields(session, local, item, result)
    result.trips_updated += 1


def import_diary(
    session: Session,
    data: dict[str, Any],
    *,
    make_backup: bool = True,
    family: bool = False,
) -> DiaryImportResult:
    """Idempotentní sloučení. Neznámé place_id uloží návštěvu, nevytvoří Place."""
    validate_diary(data)
    result = DiaryImportResult()
    if make_backup:
        result.backup_path = backup_before_import(session, "diary")

    relink_unknown_diary_rows(session)

    for item in data.get("visits") or []:
        if isinstance(item, dict):
            _merge_visit(session, item, result)
    for item in data.get("place_states") or []:
        if isinstance(item, dict):
            if family:
                _merge_state_family(session, item, result)
            else:
                _merge_state(session, item, result)
    for item in data.get("trips") or []:
        if isinstance(item, dict):
            _merge_trip(session, item, result)

    if family:
        from app.services.family_merge import collapse_family_visits

        result.family_collapsed = collapse_family_visits(session)

    _set_meta(session, META_DIARY_IMPORT_AT, now_iso())
    session.commit()
    _log.info(
        "diary imported visits +%s ~%s =%s states +%s ~%s =%s trips +%s ~%s =%s unknown=%s",
        result.visits_inserted,
        result.visits_updated,
        result.visits_unchanged,
        result.states_inserted,
        result.states_updated,
        result.states_unchanged,
        result.trips_inserted,
        result.trips_updated,
        result.trips_unchanged,
        len(result.unknown_place_ids),
    )
    return result


def visit_to_json(visit: Visit) -> dict[str, Any]:
    return {
        "id": visit.public_id,
        "place_id": visit.place_public_id,
        "visited_at": visit.visited_at,
        "rating": visit.rating,
        "people": visit.people,
        "note": visit.note,
        "trip_id": visit.trip_public_id,
        "created_at": visit.created_at,
        "updated_at": visit.updated_at,
        "deleted_at": visit.deleted_at,
    }


def state_to_json(state: PlaceJournalState) -> dict[str, Any]:
    return {
        "place_id": state.place_public_id,
        "want_to_visit": bool(state.want_to_visit),
        "favorite": bool(state.favorite),
        "personal_note": state.personal_note,
        "updated_at": state.updated_at,
        "deleted_at": state.deleted_at,
    }


def trip_to_json(trip: Trip) -> dict[str, Any]:
    origin = trip.origin
    return {
        "id": trip.public_id,
        "name": trip.name,
        "planned_on": trip.planned_on,
        "origin": (
            {
                "latitude": origin["latitude"],
                "longitude": origin["longitude"],
                "label": origin["label"],
            }
            if origin is not None
            else None
        ),
        "notes": trip.notes,
        "status": trip.status or "planned",
        "stops": [
            {
                "place_id": stop.place_public_id,
                "sort_order": stop.sort_order,
                "note": stop.note,
            }
            for stop in sorted(trip.stops, key=lambda item: (item.sort_order, item.id))
        ],
        "created_at": trip.created_at,
        "updated_at": trip.updated_at,
        "deleted_at": trip.deleted_at,
    }


def build_diary(session: Session, exported_from: str = "pc") -> dict[str, Any]:
    visits = list(session.scalars(select(Visit).order_by(Visit.created_at.asc(), Visit.id.asc())).all())
    states = list(
        session.scalars(
            select(PlaceJournalState).order_by(PlaceJournalState.place_public_id.asc())
        ).all()
    )
    trips = list(session.scalars(select(Trip).order_by(Trip.created_at.asc(), Trip.id.asc())).all())
    diary = {
        "schema_version": SCHEMA_VERSION,
        "exported_at": now_iso(),
        "exported_from": exported_from,
        "place_states": [state_to_json(row) for row in states],
        "visits": [visit_to_json(row) for row in visits],
        "trips": [trip_to_json(row) for row in trips],
    }
    validate_diary(diary)
    return diary


def export_diary(session: Session, path: Path | None = None) -> DiaryExportResult:
    target = path or get_default_diary_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    diary = build_diary(session, exported_from="pc")
    target.write_text(json.dumps(diary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _set_meta(session, META_DIARY_EXPORT_AT, diary["exported_at"])
    session.commit()
    _log.info("diary exported visits=%s states=%s trips=%s path=%s", len(diary["visits"]), len(diary["place_states"]), len(diary["trips"]), target)
    return DiaryExportResult(
        path=target,
        visit_count=len(diary["visits"]),
        state_count=len(diary["place_states"]),
        diary=diary,
    )


def export_diary_zip(session: Session) -> bytes:
    from app.services.diary_bundle import build_diary_zip

    diary = build_diary(session, exported_from="pc")
    payload = build_diary_zip(diary)
    _set_meta(session, META_DIARY_EXPORT_AT, diary["exported_at"])
    session.commit()
    return payload


def diary_export_status(session: Session) -> dict[str, Any]:
    return {
        "last_import_at": _get_meta(session, META_DIARY_IMPORT_AT),
        "last_export_at": _get_meta(session, META_DIARY_EXPORT_AT),
        "default_path": get_default_diary_path(),
        "open_issue_count": session.scalar(
            select(func.count()).select_from(DiaryImportIssue).where(DiaryImportIssue.resolved_at.is_(None))
        )
        or 0,
    }


def list_open_diary_issues(session: Session) -> list[DiaryImportIssue]:
    return list(
        session.scalars(
            select(DiaryImportIssue)
            .where(DiaryImportIssue.resolved_at.is_(None))
            .order_by(DiaryImportIssue.created_at.desc())
        ).all()
    )


def list_visits_for_place(session: Session, place: Place, *, include_deleted: bool = False) -> list[Visit]:
    stmt = select(Visit).where(Visit.place_public_id == place.public_id)
    if not include_deleted:
        stmt = stmt.where(Visit.deleted_at.is_(None))
    return list(session.scalars(stmt.order_by(Visit.visited_at.desc(), Visit.created_at.desc())).all())


VISIT_PAGE_SIZE = 50
_VISIT_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _valid_iso_date(raw: str) -> str:
    if not _VISIT_DATE_RE.fullmatch(raw):
        return ""
    try:
        datetime.strptime(raw, "%Y-%m-%d")
    except ValueError:
        return ""
    return raw


@dataclass
class VisitFilters:
    q: str = ""
    date_from: str = ""
    date_to: str = ""
    rating: int | None = None
    include_deleted: bool = False
    page: int = 1

    @classmethod
    def from_query(cls, params) -> VisitFilters:
        try:
            page = int(params.get("page") or 1)
        except (TypeError, ValueError):
            page = 1
        rating_raw = str(params.get("rating") or "").strip()
        rating: int | None
        try:
            rating = int(rating_raw) if rating_raw else None
        except ValueError:
            rating = None
        if rating not in {1, 2, 3, 4, 5}:
            rating = None
        deleted = str(params.get("deleted") or "").strip().lower()
        return cls(
            q=str(params.get("q") or "").strip(),
            date_from=_valid_iso_date(str(params.get("date_from") or "").strip()),
            date_to=_valid_iso_date(str(params.get("date_to") or "").strip()),
            rating=rating,
            include_deleted=deleted in {"1", "on", "true", "yes"},
            page=max(page, 1),
        )

    def query_string(self, page: int | None = None) -> str:
        pairs: list[tuple[str, str]] = []
        if self.q:
            pairs.append(("q", self.q))
        if self.date_from:
            pairs.append(("date_from", self.date_from))
        if self.date_to:
            pairs.append(("date_to", self.date_to))
        if self.rating is not None:
            pairs.append(("rating", str(self.rating)))
        if self.include_deleted:
            pairs.append(("deleted", "1"))
        shown_page = self.page if page is None else page
        if shown_page > 1:
            pairs.append(("page", str(shown_page)))
        return urlencode(pairs)

    def is_filtered(self) -> bool:
        return bool(self.q or self.date_from or self.date_to or self.rating is not None or self.include_deleted)


@dataclass
class VisitListResult:
    visits: list[Visit]
    total: int
    page: int
    pages: int
    per_page: int


def _visit_clauses(filters: VisitFilters) -> list:
    clauses: list = []
    if not filters.include_deleted:
        clauses.append(Visit.deleted_at.is_(None))
    if filters.q:
        needle = f"%{filters.q}%"
        clauses.append(
            or_(
                Visit.place_public_id.ilike(needle),
                Visit.place.has(Place.name.ilike(needle)),
                Visit.place.has(Place.municipality.ilike(needle)),
            )
        )
    if filters.date_from:
        clauses.append(Visit.visited_at.is_not(None))
        clauses.append(Visit.visited_at >= filters.date_from)
    if filters.date_to:
        clauses.append(Visit.visited_at.is_not(None))
        clauses.append(Visit.visited_at <= filters.date_to)
    if filters.rating is not None:
        clauses.append(Visit.rating == filters.rating)
    return clauses


def list_visits(session: Session, filters: VisitFilters) -> VisitListResult:
    clauses = _visit_clauses(filters)
    count_stmt = select(func.count()).select_from(Visit)
    stmt = select(Visit).options(joinedload(Visit.place))
    if clauses:
        count_stmt = count_stmt.where(*clauses)
        stmt = stmt.where(*clauses)
    total = session.scalar(count_stmt) or 0
    pages = max(1, (total + VISIT_PAGE_SIZE - 1) // VISIT_PAGE_SIZE) if total else 1
    page = min(filters.page, pages)
    stmt = (
        stmt.order_by(Visit.visited_at.desc().nullslast(), Visit.created_at.desc())
        .offset((page - 1) * VISIT_PAGE_SIZE)
        .limit(VISIT_PAGE_SIZE)
    )
    rows = list(session.scalars(stmt).unique().all())
    return VisitListResult(visits=rows, total=total, page=page, pages=pages, per_page=VISIT_PAGE_SIZE)


class VisitInputError(ValueError):
    """Neplatný formulář návštěvy. Nic se neuložilo."""


def today_iso_date() -> str:
    return now_iso()[:10]


def parse_people(raw: str) -> list[str]:
    seen: set[str] = set()
    names: list[str] = []
    for part in re.split(r"[,;\n]", raw or ""):
        name = part.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names


def parse_rating(raw: str) -> int | None:
    value = (raw or "").strip()
    if not value:
        return None
    try:
        rating = int(value)
    except ValueError as exc:
        raise VisitInputError("Hodnocení musí být 1–5.") from exc
    if rating not in {1, 2, 3, 4, 5}:
        raise VisitInputError("Hodnocení musí být 1–5.")
    return rating


def _parse_visited_at(raw: str | None) -> str:
    date_value = (raw or "").strip() or today_iso_date()
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date_value):
        raise VisitInputError("Datum musí být ve formátu RRRR-MM-DD.")
    try:
        datetime.strptime(date_value, "%Y-%m-%d")
    except ValueError as exc:
        raise VisitInputError("Neplatné datum.") from exc
    return date_value


def add_visit(
    session: Session,
    place: Place,
    *,
    visited_at: str | None,
    rating: int | None,
    people: str,
    note: str | None,
) -> Visit:
    """Nová návštěva s vlastním UUIDv7. Neodvozuje id z místa. Stejný den může mít víc záznamů."""
    date_value = _parse_visited_at(visited_at)
    if rating is not None and rating not in {1, 2, 3, 4, 5}:
        raise VisitInputError("Hodnocení musí být 1–5.")
    now = now_iso()
    visit = Visit(
        public_id=new_public_id(),
        place_id=place.id,
        place_public_id=place.public_id,
        visited_at=date_value,
        rating=rating,
        people_json=_people_json(parse_people(people)),
        note=(note or "").strip() or None,
        created_at=now,
        updated_at=now,
        deleted_at=None,
    )
    session.add(visit)
    session.commit()
    session.refresh(visit)
    _log.info("visit added id=%s place=%s", visit.public_id, place.public_id)
    return visit


def update_visit(
    session: Session,
    visit: Visit,
    *,
    visited_at: str | None,
    rating: int | None,
    people: str,
    note: str | None,
) -> Visit:
    """Úprava existující návštěvy. Soft-smazanou nepřepisuje."""
    if visit.deleted_at:
        raise VisitInputError("Smazanou návštěvu nelze upravit.")
    if rating is not None and rating not in {1, 2, 3, 4, 5}:
        raise VisitInputError("Hodnocení musí být 1–5.")
    visit.visited_at = _parse_visited_at(visited_at)
    visit.rating = rating
    visit.people_json = _people_json(parse_people(people))
    visit.note = (note or "").strip() or None
    visit.updated_at = now_iso()
    session.commit()
    session.refresh(visit)
    _log.info("visit updated id=%s", visit.public_id)
    return visit


def get_visit_for_place(session: Session, place: Place, visit_public_id: str) -> Visit | None:
    return session.scalar(
        select(Visit).where(
            Visit.public_id == visit_public_id,
            Visit.place_public_id == place.public_id,
        )
    )


def soft_delete_visit(session: Session, visit: Visit) -> Visit:
    """Soft-delete: nastaví deleted_at, fyzicky nemaže. Stejné chování jako PWA."""
    if visit.deleted_at:
        return visit
    now = now_iso()
    visit.deleted_at = now
    visit.updated_at = now
    session.commit()
    _log.info("visit soft-deleted id=%s", visit.public_id)
    return visit


def save_journal_state(
    session: Session,
    place: Place,
    *,
    want_to_visit: bool,
    favorite: bool,
    personal_note: str | None,
) -> PlaceJournalState:
    """Osobní stav místa. Nemění master sloupce Place."""
    state = session.scalar(
        select(PlaceJournalState).where(PlaceJournalState.place_public_id == place.public_id)
    )
    now = now_iso()
    if state is None:
        state = PlaceJournalState(place_public_id=place.public_id)
        session.add(state)
    state.place_id = place.id
    state.want_to_visit = 1 if want_to_visit else 0
    state.favorite = 1 if favorite else 0
    state.personal_note = (personal_note or "").strip() or None
    state.updated_at = now
    state.deleted_at = None
    session.commit()
    session.refresh(state)
    _log.info("journal state saved place=%s", place.public_id)
    return state
