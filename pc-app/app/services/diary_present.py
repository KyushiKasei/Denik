"""Pas, odznaky, ročenka, atlas a dnešní výlet — stejná logika jako PWA."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.db.enums import label
from app.db.models import Place, PlaceJournalState, Trip, Visit
from app.services.czech_regions import CZECH_REGIONS, CzechRegion, match_czech_region
from app.services.diary_io import today_iso_date
from app.services.geo import haversine_km
from app.services.stamp_art import WANT_WAX, stamp_art_for_place, wax_color_for_region
from app.services.trips import list_trips, list_upcoming_trips

MAX_EMPTY_SLOTS = 6
PLACE_MILESTONES = (5, 10, 25, 50)
FIRST_TYPE_ORDER = (
    "CASTLE",
    "CHATEAU",
    "RUIN",
    "FORTRESS",
    "MANOR",
    "PALACE",
    "LOOKOUT_TOWER",
    "ZOO",
    "CAVE",
)
FIRST_TYPE_TITLE = {
    "CASTLE": "První hrad",
    "CHATEAU": "První zámek",
    "RUIN": "První zřícenina",
    "FORTRESS": "První pevnost",
    "MANOR": "První tvrz",
    "PALACE": "První palác",
    "LOOKOUT_TOWER": "První rozhledna",
    "ZOO": "První zoo",
    "CAVE": "První jeskyně",
}
ATLAS_CENTER_LAT = 49.817
ATLAS_CENTER_LON = 15.473
UNTIL_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@dataclass(frozen=True)
class PassportStamp:
    place_id: str
    visit_id: str
    name: str
    visited_at: str | None
    kind: str
    wax: str


@dataclass(frozen=True)
class PassportPage:
    region: CzechRegion
    visited: int
    total: int
    stamps: list[PassportStamp]
    empty_slots: int


@dataclass(frozen=True)
class RegionProgress:
    region: CzechRegion
    visited: int
    total: int
    unlocked: bool


@dataclass(frozen=True)
class DiaryBadge:
    id: str
    title: str
    detail: str
    unlocked: bool


@dataclass(frozen=True)
class YearbookRated:
    place_id: str
    name: str
    rating: int


@dataclass(frozen=True)
class YearbookStats:
    year: int
    visit_count: int
    unique_places: int
    favorite_visits: int
    trip_count: int
    top_rated: list[YearbookRated]
    people: list[str]


@dataclass(frozen=True)
class TripTodayStop:
    place_id: str
    name: str
    done: bool
    stamped_today: bool
    km_from_here: float | None


@dataclass(frozen=True)
class TripTodayProgress:
    trip: Trip
    stops: list[TripTodayStop]
    next_stop: TripTodayStop | None
    done_count: int
    all_done: bool
    air_km: float | None


def active_places(session: Session) -> list[Place]:
    return list(session.scalars(select(Place).where(Place.archived_at.is_(None))).all())


def live_visits(session: Session) -> list[Visit]:
    return list(
        session.scalars(
            select(Visit)
            .where(Visit.deleted_at.is_(None))
            .options(joinedload(Visit.place))
            .order_by(Visit.visited_at.asc().nullslast(), Visit.created_at.asc())
        )
        .unique()
        .all()
    )


def unique_visited_place_ids(visits: list[Visit]) -> set[str]:
    return {visit.place_public_id for visit in visits if not visit.deleted_at}


def favorite_place_ids(session: Session) -> set[str]:
    rows = session.scalars(
        select(PlaceJournalState).where(
            PlaceJournalState.deleted_at.is_(None),
            PlaceJournalState.favorite == 1,
        )
    ).all()
    return {row.place_public_id for row in rows}


def stamp_from_visit(visit: Visit) -> PassportStamp:
    place = visit.place
    kind, wax = stamp_art_for_place(place)
    return PassportStamp(
        place_id=visit.place_public_id,
        visit_id=visit.public_id,
        name=place.name if place is not None else "Místo",
        visited_at=visit.visited_at,
        kind=kind,
        wax=wax,
    )


def passport_pages(places: list[Place], visits: list[Visit]) -> list[PassportPage]:
    totals: dict[str, int] = {region.id: 0 for region in CZECH_REGIONS}
    stamps_by_region: dict[str, list[PassportStamp]] = {region.id: [] for region in CZECH_REGIONS}
    for place in places:
        region = match_czech_region(place.region)
        if region is None:
            continue
        totals[region.id] += 1

    seen_place: set[str] = set()
    live = [visit for visit in visits if not visit.deleted_at]
    live.sort(key=lambda visit: (visit.visited_at or "", visit.created_at))
    for visit in live:
        if visit.place_public_id in seen_place:
            continue
        seen_place.add(visit.place_public_id)
        place = visit.place
        region = match_czech_region(place.region if place is not None else None)
        if region is None:
            continue
        stamps_by_region[region.id].append(stamp_from_visit(visit))

    pages: list[PassportPage] = []
    for region in CZECH_REGIONS:
        stamps = stamps_by_region[region.id]
        total = totals[region.id]
        remaining = max(0, total - len(stamps))
        pages.append(
            PassportPage(
                region=region,
                visited=len(stamps),
                total=total,
                stamps=stamps,
                empty_slots=min(MAX_EMPTY_SLOTS, remaining),
            )
        )
    return pages


def page_for_region(pages: list[PassportPage], region_id: str | None) -> PassportPage | None:
    if not pages:
        return None
    if region_id:
        for page in pages:
            if page.region.id == region_id:
                return page
    for page in pages:
        if page.stamps:
            return page
    return pages[0]


def region_progress(places: list[Place], visits: list[Visit]) -> list[RegionProgress]:
    visited_ids = unique_visited_place_ids(visits)
    totals = {region.id: 0 for region in CZECH_REGIONS}
    seen = {region.id: 0 for region in CZECH_REGIONS}
    for place in places:
        region = match_czech_region(place.region)
        if region is None:
            continue
        totals[region.id] += 1
        if place.public_id in visited_ids:
            seen[region.id] += 1
    return [
        RegionProgress(
            region=region,
            visited=seen[region.id],
            total=totals[region.id],
            unlocked=seen[region.id] > 0,
        )
        for region in CZECH_REGIONS
    ]


def _czech_places_word(count: int) -> str:
    if count == 1:
        return "místo"
    if 2 <= count <= 4:
        return "místa"
    return "míst"


def _czech_kraje_word(count: int) -> str:
    if count == 1:
        return "kraj"
    if 2 <= count <= 4:
        return "kraje"
    return "krajů"


def compute_badges(visits: list[Visit], places: list[Place]) -> list[DiaryBadge]:
    live = [visit for visit in visits if not visit.deleted_at]
    unique_ids = unique_visited_place_ids(live)
    unique_count = len(unique_ids)
    places_by_id = {place.public_id: place for place in places}
    visited_places = [places_by_id[place_id] for place_id in unique_ids if place_id in places_by_id]
    visited_types = {item.code for place in visited_places for item in place.types}
    visited_unesco = any(place.unesco for place in visited_places)
    regions = {place.region.strip() for place in visited_places if place.region and place.region.strip()}

    badges: list[DiaryBadge] = [
        DiaryBadge(
            id="first_visit",
            title="První návštěva",
            detail="V deníku je alespoň jedna návštěva." if unique_count > 0 else "Zapište první návštěvu u místa.",
            unlocked=unique_count > 0,
        )
    ]
    for n in PLACE_MILESTONES:
        badges.append(
            DiaryBadge(
                id=f"places_{n}",
                title=f"{n} navštívených míst",
                detail=(
                    f"Navštíveno {n} {_czech_places_word(n)}."
                    if unique_count >= n
                    else f"Zatím {unique_count} {_czech_places_word(unique_count)}."
                ),
                unlocked=unique_count >= n,
            )
        )
    badges.append(
        DiaryBadge(
            id="unesco",
            title="Návštěva UNESCO",
            detail="V deníku je místo ze seznamu UNESCO." if visited_unesco else "Zatím bez navštíveného UNESCO.",
            unlocked=visited_unesco,
        )
    )
    if regions:
        badges.append(
            DiaryBadge(
                id="regions",
                title=f"Navštíveno {len(regions)} {_czech_kraje_word(len(regions))}",
                detail=", ".join(sorted(regions)),
                unlocked=True,
            )
        )
    for type_code in FIRST_TYPE_ORDER:
        unlocked = type_code in visited_types
        badges.append(
            DiaryBadge(
                id=f"first_{type_code.lower()}",
                title=FIRST_TYPE_TITLE[type_code],
                detail=(
                    f"V deníku je návštěva: {label('place_types', type_code)}."
                    if unlocked
                    else f"Zatím bez typu {label('place_types', type_code)}."
                ),
                unlocked=unlocked,
            )
        )
    return badges


def badges_for_display(badges: list[DiaryBadge]) -> list[DiaryBadge]:
    unlocked = [badge for badge in badges if badge.unlocked]
    if not unlocked:
        return []
    next_milestone = next((badge for badge in badges if badge.id.startswith("places_") and not badge.unlocked), None)
    if next_milestone is not None and all(badge.id != next_milestone.id for badge in unlocked):
        return [*unlocked, next_milestone]
    return unlocked


def visit_year(visited_at: str | None, fallback_year: int) -> int | None:
    if not visited_at:
        return fallback_year
    if len(visited_at) >= 4 and visited_at[:4].isdigit():
        return int(visited_at[:4])
    return None


def current_year(now: datetime | None = None) -> int:
    return (now or datetime.now().astimezone()).year


def yearbook_for(
    year: int,
    visits: list[Visit],
    places: list[Place],
    trips: list[Trip],
    favorite_ids: set[str],
) -> YearbookStats:
    places_by_id = {place.public_id: place for place in places}
    live = [visit for visit in visits if not visit.deleted_at and visit_year(visit.visited_at, year) == year]
    people: set[str] = set()
    for visit in live:
        people.update(visit.people)
    rated = [visit for visit in live if visit.rating is not None]
    rated.sort(key=lambda visit: (-(visit.rating or 0), visit.visited_at or ""))
    top_rated = [
        YearbookRated(
            place_id=visit.place_public_id,
            name=places_by_id[visit.place_public_id].name if visit.place_public_id in places_by_id else "Místo",
            rating=visit.rating or 0,
        )
        for visit in rated[:3]
    ]
    year_trips = [trip for trip in trips if not trip.is_deleted and (trip.planned_on or "").startswith(str(year))]
    return YearbookStats(
        year=year,
        visit_count=len(live),
        unique_places=len(unique_visited_place_ids(live)),
        favorite_visits=sum(1 for visit in live if visit.place_public_id in favorite_ids),
        trip_count=len(year_trips),
        top_rated=top_rated,
        people=sorted(people),
    )


def parse_until_param(value: str | None) -> str | None:
    raw = (value or "").strip()
    if not UNTIL_DATE.fullmatch(raw):
        return None
    try:
        datetime.strptime(raw, "%Y-%m-%d")
    except ValueError:
        return None
    return raw


def atlas_timeline(visits: list[Visit], *, region_raw: str | None = None) -> list[dict]:
    wanted = match_czech_region(region_raw) if region_raw else None
    live = [visit for visit in visits if not visit.deleted_at]
    live.sort(key=lambda visit: (visit.visited_at is None, visit.visited_at or "", visit.created_at))
    events: list[dict] = []
    for visit in live:
        place = visit.place
        if place is None or place.latitude is None or place.longitude is None:
            continue
        if wanted is not None:
            region = match_czech_region(place.region)
            if region is None or region.id != wanted.id:
                continue
        events.append(
            {
                "visit_id": visit.public_id,
                "id": visit.place_public_id,
                "name": place.name,
                "lat": place.latitude,
                "lon": place.longitude,
                "visited_at": visit.visited_at,
                "color": wax_color_for_region(place.region),
            }
        )
    return events


def timeline_index_for_until(timeline: list[dict], until: str | None) -> int | None:
    if not until:
        return None
    last = -1
    for index, event in enumerate(timeline):
        at = event.get("visited_at")
        if at and at <= until:
            last = index
    return last


def atlas_markers(session: Session, *, region_raw: str | None = None) -> list[dict]:
    wanted = match_czech_region(region_raw) if region_raw else None
    include_other = wanted is not None
    markers: list[dict] = []
    for place in active_places(session):
        if place.latitude is None or place.longitude is None:
            continue
        region = match_czech_region(place.region)
        if wanted is not None and (region is None or region.id != wanted.id):
            continue
        visited = place.is_visited
        want = place.wants_visit
        if not include_other and not visited and not want:
            continue
        kind = "visited" if visited else "want" if want else "other"
        color = wax_color_for_region(place.region) if visited else WANT_WAX if want else "#6a6258"
        markers.append(
            {
                "id": place.public_id,
                "name": place.name,
                "lat": place.latitude,
                "lon": place.longitude,
                "km": None,
                "visited": visited,
                "want": want,
                "kind": kind,
                "color": color,
            }
        )
    return markers


def pick_trip_today(session: Session) -> Trip | None:
    today = today_iso_date()
    trips = [trip for trip in list_trips(session) if trip.stops]
    for trip in trips:
        if trip.planned_on == today:
            return trip
    upcoming = [trip for trip in list_upcoming_trips(session) if trip.stops]
    return upcoming[0] if upcoming else None


def trip_today_progress(
    trip: Trip,
    visits: list[Visit],
    today: str,
    here: tuple[float, float] | None = None,
) -> TripTodayProgress:
    visited_ids = unique_visited_place_ids(visits)
    today_ids = {
        visit.place_public_id
        for visit in visits
        if not visit.deleted_at and visit.visited_at == today
    }
    stops: list[TripTodayStop] = []
    for stop in trip.stops:
        place = stop.place
        km = None
        if here is not None and place is not None:
            km = haversine_km(here[0], here[1], place.latitude, place.longitude)
        stops.append(
            TripTodayStop(
                place_id=stop.place_public_id,
                name=place.name if place is not None else "Místo",
                done=stop.place_public_id in visited_ids,
                stamped_today=stop.place_public_id in today_ids,
                km_from_here=km,
            )
        )
    next_stop = next((stop for stop in stops if not stop.done), None)
    known_km: list[float] = []
    for index, stop in enumerate(stops):
        if index == 0:
            continue
        previous = trip.stops[index - 1].place
        current = trip.stops[index].place
        if previous is None or current is None:
            continue
        gap = haversine_km(previous.latitude, previous.longitude, current.latitude, current.longitude)
        if gap is not None:
            known_km.append(gap)
    return TripTodayProgress(
        trip=trip,
        stops=stops,
        next_stop=next_stop,
        done_count=sum(1 for stop in stops if stop.done),
        all_done=bool(stops) and all(stop.done for stop in stops),
        air_km=sum(known_km) if known_km else None,
    )


def recent_stamps(visits: list[Visit], *, limit: int = 6) -> list[PassportStamp]:
    newest = sorted(
        [visit for visit in visits if not visit.deleted_at],
        key=lambda visit: (visit.visited_at or "", visit.created_at),
        reverse=True,
    )
    seen: set[str] = set()
    stamps: list[PassportStamp] = []
    for visit in newest:
        if visit.place_public_id in seen:
            continue
        seen.add(visit.place_public_id)
        stamps.append(stamp_from_visit(visit))
        if len(stamps) >= limit:
            break
    return stamps


def format_visit_date(visited_at: str | None) -> str:
    if not visited_at:
        return "bez data"
    if len(visited_at) >= 10 and visited_at[4] == "-" and visited_at[7] == "-":
        year, month, day = visited_at[:4], visited_at[5:7], visited_at[8:10]
        if year.isdigit() and month.isdigit() and day.isdigit():
            return f"{int(day)}. {int(month)}. {year}"
    return visited_at
