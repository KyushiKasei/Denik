from __future__ import annotations

from app.db.models import Place
from app.services.czech_regions import match_czech_region
from app.services.diary_io import add_visit, save_journal_state, today_iso_date
from app.services.diary_present import (
    active_places,
    atlas_markers,
    atlas_timeline,
    badges_for_display,
    compute_badges,
    current_year,
    live_visits,
    page_for_region,
    parse_until_param,
    passport_pages,
    pick_trip_today,
    region_progress,
    timeline_index_for_until,
    trip_today_progress,
    yearbook_for,
)
from app.services.places import PlaceInput, create_place
from app.services.stamp_art import stamp_kind_from_types, wax_color_for_region
from app.services.trips import add_stop, create_trip
from sqlalchemy.orm import Session


def _place(session: Session, name: str, *, region: str, types: list[str] | None = None, unesco: bool = False) -> Place:
    return create_place(
        session,
        PlaceInput(
            name=name,
            condition="PRESERVED",
            visitability="REGULAR",
            quality_status="VERIFIED",
            municipality=name,
            country="CZ",
            region=region,
            type_codes=types or ["CASTLE"],
            unesco=unesco,
            latitude=49.7,
            longitude=16.8,
        ),
    )


def test_hrad_ma_prednost_a_vosk_podle_kraje() -> None:
    assert stamp_kind_from_types(["CASTLE", "CHATEAU"]) == "castle"
    assert stamp_kind_from_types(["CASTLE", "RUIN"]) == "ruin"
    assert wax_color_for_region("Olomoucký kraj") == "#2e5a4a"
    assert wax_color_for_region("Atlantis") == "#3d5a40"
    assert match_czech_region("Olomoucký kraj") is not None
    assert match_czech_region("Olomoucký kraj").id == "OLK"


def test_shared_region_and_stamp_json() -> None:
    from app.services.czech_regions import CZECH_REGIONS
    from app.services.stamp_art import DEFAULT_WAX, REGION_WAX, STAMP_PATHS

    assert len(CZECH_REGIONS) == 14
    assert {row.id for row in CZECH_REGIONS} == set(REGION_WAX)
    assert "castle" in STAMP_PATHS
    assert DEFAULT_WAX == "#3d5a40"


def test_pas_seskupi_otisky_podle_kraje(session: Session) -> None:
    a = _place(session, "Bouzov", region="Olomoucký kraj")
    b = _place(session, "Šternberk", region="Olomoucký kraj")
    add_visit(session, a, visited_at="2026-08-09", rating=None, people="", note=None)
    add_visit(session, a, visited_at="2026-08-10", rating=None, people="", note=None)
    add_visit(session, b, visited_at="2026-08-11", rating=None, people="", note=None)
    pages = passport_pages(active_places(session), live_visits(session))
    olk = next(page for page in pages if page.region.id == "OLK")
    assert len(olk.stamps) == 2
    assert sorted(stamp.name for stamp in olk.stamps) == ["Bouzov", "Šternberk"]
    assert olk.total == 2
    assert page_for_region(pages, "OLK") is olk


def test_odznaky_prvni_navsteva_a_kraj(session: Session) -> None:
    castle = _place(session, "Bouzov", region="Olomoucký kraj")
    visit = add_visit(session, castle, visited_at="2026-08-09", rating=None, people="", note=None)
    badges = compute_badges([visit], [castle])
    unlocked = {badge.id for badge in badges if badge.unlocked}
    assert "first_visit" in unlocked
    assert "first_castle" in unlocked
    assert "regions" in unlocked
    assert "places_5" not in unlocked
    shown = badges_for_display(badges)
    assert any(badge.id == "first_visit" for badge in shown)
    assert [badge.id for badge in shown if badge.id.startswith("places_")] == ["places_5"]


def test_rocenka_pocita_rok_a_lidi(session: Session) -> None:
    place = _place(session, "Bouzov", region="Olomoucký kraj")
    add_visit(session, place, visited_at="2026-08-09", rating=5, people="Petr, Jana", note=None)
    add_visit(session, place, visited_at="2025-01-01", rating=3, people="Petr", note=None)
    stats = yearbook_for(2026, live_visits(session), active_places(session), [], set())
    assert stats.visit_count == 1
    assert stats.unique_places == 1
    assert stats.people == ["Jana", "Petr"]
    assert stats.top_rated[0].name == "Bouzov"


def test_dnesni_vylet_oznaci_hotove_zastavky(session: Session) -> None:
    first = _place(session, "Bouzov", region="Olomoucký kraj")
    second = _place(session, "Šternberk", region="Olomoucký kraj", types=["CHATEAU"])
    trip = create_trip(session, name="Okruh", planned_on=today_iso_date())
    add_stop(session, trip, first)
    add_stop(session, trip, second)
    visit = add_visit(session, first, visited_at=today_iso_date(), rating=None, people="", note=None)
    picked = pick_trip_today(session)
    assert picked is not None
    progress = trip_today_progress(picked, [visit], today_iso_date())
    assert progress.done_count == 1
    assert progress.next_stop is not None
    assert progress.next_stop.name == "Šternberk"
    rows = region_progress([first, second], [visit])
    olk = next(row for row in rows if row.region.id == "OLK")
    assert olk.visited == 1
    assert olk.unlocked
    assert current_year() >= 2026


def test_atlas_timeline_radi_datum_bez_data_a_until(session: Session) -> None:
    bouzov = _place(session, "Bouzov", region="Olomoucký kraj")
    krumlov = _place(session, "Český Krumlov", region="Jihočeský kraj")
    ghost = create_place(
        session,
        PlaceInput(
            name="Bez GPS",
            condition="PRESERVED",
            visitability="REGULAR",
            quality_status="VERIFIED",
            municipality="Obec",
            country="CZ",
            region="Olomoucký kraj",
            type_codes=["CASTLE"],
            latitude=None,
            longitude=None,
        ),
    )
    first = add_visit(session, krumlov, visited_at="2022-07-09", rating=None, people="", note=None)
    second = add_visit(session, bouzov, visited_at="2024-06-15", rating=None, people="", note=None)
    third = add_visit(session, bouzov, visited_at="2025-07-12", rating=None, people="", note=None)
    add_visit(session, ghost, visited_at="2023-01-01", rating=None, people="", note=None)
    dateless = add_visit(session, bouzov, visited_at="2026-01-02", rating=None, people="", note=None)
    dateless.visited_at = None
    session.flush()
    lednice = _place(session, "Lednice", region="Jihomoravský kraj")
    save_journal_state(session, lednice, want_to_visit=True, favorite=False, personal_note=None)

    timeline = atlas_timeline(live_visits(session))
    assert [event["visit_id"] for event in timeline] == [
        first.public_id,
        second.public_id,
        third.public_id,
        dateless.public_id,
    ]
    assert timeline[0]["name"] == "Český Krumlov"
    assert timeline[-1]["visited_at"] is None
    assert timeline[1]["color"] == "#2e5a4a"

    assert parse_until_param("2024-12-31") == "2024-12-31"
    assert parse_until_param("nope") is None
    assert timeline_index_for_until(timeline, None) is None
    assert timeline_index_for_until(timeline, "2020-01-01") == -1
    assert timeline_index_for_until(timeline, "2024-12-31") == 1

    session.expire_all()
    markers = atlas_markers(session)
    visited = [row for row in markers if row["visited"]]
    want = [row for row in markers if row["want"] and not row["visited"]]
    assert {row["name"] for row in visited} == {"Bouzov", "Český Krumlov"}
    assert {row["name"] for row in want} == {"Lednice"}
    assert next(row["color"] for row in visited if row["name"] == "Bouzov") == "#2e5a4a"
