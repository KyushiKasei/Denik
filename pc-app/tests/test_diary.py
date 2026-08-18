from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import REPO_ROOT, get_default_diary_path
from app.db.models import DiaryImportIssue, Place, PlaceJournalState, Trip, TripStop, Visit
from app.services.diary_io import (
    VisitInputError,
    add_visit,
    export_diary,
    import_diary,
    list_visits_for_place,
    parse_people,
    save_journal_state,
    soft_delete_visit,
    visit_to_json,
)
from app.services.diary_schema import DiarySchemaError, load_and_validate_diary, validate_diary
from app.services.merge_places import merge_places
from app.services.places import PlaceFilters, PlaceInput, archive_place, create_place, dashboard_stats, list_places

SAMPLE_DIARY = REPO_ROOT / "fixtures" / "diary.sample.json"
BOUZOV_ID = "0198f23a-5e5e-7b31-a8be-8c99507a2138"
VISIT_A = "0198f93b-618d-762f-a589-ccf375139dd9"
VISIT_B = "0198f93b-618d-762f-a589-ccf375139dda"
TRIP_A = "0198f93b-618d-762f-a589-ccf375139dd8"
UNKNOWN_PLACE = "0198f23a-5e5e-7b31-a8be-8c99507a9999"


def _place_input(**overrides) -> PlaceInput:
    data = PlaceInput(
        name="Bouzov",
        condition="PRESERVED",
        visitability="REGULAR",
        quality_status="VERIFIED",
        municipality="Bouzov",
        district="Olomouc",
        region="Olomoucký kraj",
        latitude=49.704,
        longitude=16.891,
        type_codes=["CASTLE"],
    )
    for key, value in overrides.items():
        setattr(data, key, value)
    return data


def _diary(*, visits=None, states=None, trips=None, exported_from="pwa"):
    sample = json.loads(SAMPLE_DIARY.read_text(encoding="utf-8"))
    if visits is not None:
        sample["visits"] = visits
    if states is not None:
        sample["place_states"] = states
    if trips is not None:
        sample["schema_version"] = 2
        sample["trips"] = trips
    sample["exported_from"] = exported_from
    return sample


def _visit(**overrides) -> dict:
    item = json.loads(SAMPLE_DIARY.read_text(encoding="utf-8"))["visits"][0]
    item.update(overrides)
    return item


def _state(**overrides) -> dict:
    item = json.loads(SAMPLE_DIARY.read_text(encoding="utf-8"))["place_states"][0]
    item.update(overrides)
    return item


def _trip(**overrides) -> dict:
    item = {
        "id": TRIP_A,
        "name": "Olomoucko",
        "planned_on": "2026-08-20",
        "origin": None,
        "notes": None,
        "stops": [{"place_id": BOUZOV_ID, "sort_order": 0, "note": None}],
        "created_at": "2026-08-16T10:00:00+02:00",
        "updated_at": "2026-08-16T10:00:00+02:00",
        "deleted_at": None,
    }
    item.update(overrides)
    return item


def _seed_bouzov(session: Session, public_id: str = BOUZOV_ID) -> Place:
    place = Place(
        public_id=public_id,
        name="Bouzov",
        condition="PRESERVED",
        visitability="REGULAR",
        quality_status="VERIFIED",
        municipality="Bouzov",
        district="Olomouc",
        region="Olomoucký kraj",
        latitude=49.704,
        longitude=16.891,
    )
    session.add(place)
    session.commit()
    session.refresh(place)
    return place


def test_sample_diary_matches_schema() -> None:
    diary = load_and_validate_diary(SAMPLE_DIARY)
    assert diary["schema_version"] == 1
    assert diary["visits"][0]["id"] == VISIT_A
    assert diary["place_states"][0]["updated_at"]
    assert "deleted_at" in diary["visits"][0]
    assert "deleted_at" in diary["place_states"][0]
    assert diary["trips"] == []


def test_schema_version_2_without_trips_is_rejected() -> None:
    sample = json.loads(SAMPLE_DIARY.read_text(encoding="utf-8"))
    with pytest.raises(DiarySchemaError, match="trips"):
        validate_diary({**sample, "schema_version": 2})


def test_invalid_diary_is_rejected(tmp_path: Path) -> None:
    sample = json.loads(SAMPLE_DIARY.read_text(encoding="utf-8"))
    with pytest.raises(DiarySchemaError, match="schema_version"):
        validate_diary({**sample, "schema_version": 99})

    integer_id = json.loads(json.dumps(sample))
    integer_id["visits"][0]["id"] = 1
    with pytest.raises(DiarySchemaError):
        validate_diary(integer_id)

    broken = tmp_path / "bad.json"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(DiarySchemaError, match="JSON"):
        load_and_validate_diary(broken)

    with pytest.raises(DiarySchemaError, match="objekt"):
        validate_diary(["not", "an", "object"])


def test_load_and_validate_diary_rejects_huge_file(tmp_path: Path, monkeypatch) -> None:
    from app.services import diary_schema

    monkeypatch.setattr(diary_schema, "MAX_DIARY_JSON_BYTES", 10)
    huge = tmp_path / "huge.json"
    huge.write_text('{"visits":[]}', encoding="utf-8")
    with pytest.raises(DiarySchemaError, match="moc velký"):
        load_and_validate_diary(huge)


def test_repeated_import_creates_zero_duplicates(session: Session) -> None:
    _seed_bouzov(session)
    data = _diary()
    first = import_diary(session, data, make_backup=False)
    second = import_diary(session, data, make_backup=False)
    assert first.visits_inserted == 1
    assert second.visits_inserted == 0
    assert second.visits_updated == 0
    assert session.scalar(select(func.count()).select_from(Visit)) == 1
    assert session.scalar(select(func.count()).select_from(PlaceJournalState)) == 1


def test_two_visits_same_place_remain_two(session: Session) -> None:
    _seed_bouzov(session)
    data = _diary(
        visits=[
            _visit(id=VISIT_A, visited_at="2026-08-09"),
            _visit(id=VISIT_B, visited_at="2026-08-10", note="Druhá návštěva."),
        ]
    )
    import_diary(session, data, make_backup=False)
    rows = list(session.scalars(select(Visit).order_by(Visit.visited_at)).all())
    assert len(rows) == 2
    assert {row.public_id for row in rows} == {VISIT_A, VISIT_B}
    assert {row.place_public_id for row in rows} == {BOUZOV_ID}


def test_family_import_collapses_same_place_and_day(session: Session) -> None:
    _seed_bouzov(session)
    import_diary(session, _diary(), make_backup=False)
    incoming = _diary(
        visits=[
            _visit(
                id=VISIT_B,
                visited_at="2026-08-09",
                people=["Eva"],
                note="Rodinná poznámka.",
                rating=4,
                created_at="2026-08-09T19:00:00+02:00",
                updated_at="2026-08-09T19:00:00+02:00",
            )
        ],
        states=[_state(want_to_visit=False, favorite=True, personal_note="Chci znovu.")],
    )
    result = import_diary(session, incoming, make_backup=False, family=True)
    assert result.family_collapsed == 1
    live = list(session.scalars(select(Visit).where(Visit.deleted_at.is_(None))).all())
    assert len(live) == 1
    winner = live[0]
    assert set(winner.people) >= {"Jana", "Petr", "Eva"}
    assert winner.note is not None
    assert "Rodinná poznámka" in winner.note
    assert winner.rating == 5
    state = session.scalar(select(PlaceJournalState))
    assert state is not None
    assert state.want_to_visit == 1
    assert state.favorite == 1
    assert state.personal_note and "Chci znovu" in state.personal_note


def test_family_collapse_tie_keeps_smaller_uuid(session: Session) -> None:
    from app.services.family_merge import collapse_family_visits

    _seed_bouzov(session)
    stamp = "2026-08-09T10:00:00+02:00"
    session.add(
        Visit(
            public_id=VISIT_B,
            place_public_id=BOUZOV_ID,
            visited_at="2026-08-09",
            people_json="[]",
            created_at=stamp,
            updated_at=stamp,
        )
    )
    session.add(
        Visit(
            public_id=VISIT_A,
            place_public_id=BOUZOV_ID,
            visited_at="2026-08-09",
            people_json="[]",
            created_at=stamp,
            updated_at=stamp,
        )
    )
    assert collapse_family_visits(session) == 1
    session.commit()
    live = list(session.scalars(select(Visit).where(Visit.deleted_at.is_(None))).all())
    assert [row.public_id for row in live] == [VISIT_A]


def test_family_collapse_moves_photos_off_loser(
    session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PAMATKY_DATA_DIR", str(tmp_path))
    from app.services.family_merge import collapse_family_visits
    from app.services.visit_photos import list_visit_photos, save_visit_photo

    _seed_bouzov(session)
    import_diary(session, _diary(), make_backup=False)
    import_diary(
        session,
        _diary(
            visits=[
                _visit(
                    id=VISIT_B,
                    visited_at="2026-08-09",
                    people=["Eva", "Petr", "Jana"],
                    note="Rodinná poznámka.",
                    rating=5,
                    created_at="2026-08-09T19:00:00+02:00",
                    updated_at="2026-08-09T19:00:00+02:00",
                )
            ]
        ),
        make_backup=False,
    )
    save_visit_photo(VISIT_A, "shot.jpg", b"jpeg-bytes")
    assert collapse_family_visits(session) == 1
    session.commit()
    live = list(session.scalars(select(Visit).where(Visit.deleted_at.is_(None))).all())
    deleted = list(session.scalars(select(Visit).where(Visit.deleted_at.is_not(None))).all())
    assert len(live) == 1
    assert len(deleted) == 1
    assert [path.name for path in list_visit_photos(live[0].public_id)] == ["shot.jpg"]
    assert list_visit_photos(deleted[0].public_id) == []


def test_family_collapse_caps_moved_photos(
    session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("PAMATKY_DATA_DIR", str(tmp_path))
    from app.services.family_merge import collapse_family_visits
    from app.services.visit_photos import MAX_PHOTOS_PER_VISIT, list_visit_photos, save_visit_photo

    _seed_bouzov(session)
    import_diary(session, _diary(), make_backup=False)
    import_diary(
        session,
        _diary(
            visits=[
                _visit(
                    id=VISIT_B,
                    visited_at="2026-08-09",
                    people=["Eva", "Petr", "Jana"],
                    note="Rodinná poznámka.",
                    rating=5,
                    created_at="2026-08-09T19:00:00+02:00",
                    updated_at="2026-08-09T19:00:00+02:00",
                )
            ]
        ),
        make_backup=False,
    )
    for index in range(MAX_PHOTOS_PER_VISIT):
        save_visit_photo(VISIT_B, f"keep{index}.jpg", b"jpeg-bytes")
    save_visit_photo(VISIT_A, "extra.jpg", b"jpeg-bytes")
    assert collapse_family_visits(session) == 1
    session.commit()
    live = list(session.scalars(select(Visit).where(Visit.deleted_at.is_(None))).all())
    deleted = list(session.scalars(select(Visit).where(Visit.deleted_at.is_not(None))).all())
    assert len(list_visit_photos(live[0].public_id)) == MAX_PHOTOS_PER_VISIT
    assert list_visit_photos(deleted[0].public_id) == []


def test_archive_place_does_not_delete_visits(session: Session) -> None:
    place = _seed_bouzov(session)
    import_diary(session, _diary(), make_backup=False)
    archive_place(session, place)
    session.refresh(place)
    assert place.archived_at is not None
    visit = session.scalar(select(Visit).where(Visit.public_id == VISIT_A))
    assert visit is not None
    assert visit.deleted_at is None
    assert visit.place_public_id == BOUZOV_ID
    assert visit.place_id == place.id
    assert session.scalar(select(func.count()).select_from(Place)) == 1


def test_unknown_place_id_does_not_create_place(session: Session) -> None:
    _seed_bouzov(session)
    before = session.scalar(select(func.count()).select_from(Place)) or 0
    data = _diary(
        visits=[_visit(place_id=UNKNOWN_PLACE)],
        states=[_state(place_id=UNKNOWN_PLACE)],
    )
    result = import_diary(session, data, make_backup=False)
    assert result.visits_inserted == 1
    assert UNKNOWN_PLACE in result.unknown_place_ids
    assert session.scalar(select(func.count()).select_from(Place)) == before
    assert session.scalar(select(Place).where(Place.public_id == UNKNOWN_PLACE)) is None
    visit = session.scalar(select(Visit).where(Visit.public_id == VISIT_A))
    assert visit is not None
    assert visit.place_id is None
    assert visit.place_public_id == UNKNOWN_PLACE
    issue = session.scalar(select(DiaryImportIssue).where(DiaryImportIssue.place_public_id == UNKNOWN_PLACE))
    assert issue is not None
    assert issue.resolved_at is None


def test_incoming_is_newer_compares_naive_and_aware() -> None:
    from datetime import datetime

    from app.services.diary_io import incoming_is_newer

    naive = "2026-08-18T12:00:00"
    same_local = datetime.fromisoformat(naive).astimezone().isoformat(timespec="seconds")
    apply, tied = incoming_is_newer(naive, same_local)
    assert apply is True
    assert tied is True
    incoming_is_newer("2026-08-18T12:00:00+02:00", naive)


def test_incoming_is_newer_strips_whitespace() -> None:
    from app.services.diary_io import incoming_is_newer

    apply, tied = incoming_is_newer(" 2026-08-18T12:00:00+02:00 ", "2026-08-18T12:00:00+02:00")
    assert apply is True
    assert tied is True


def test_newer_updated_at_wins_and_soft_delete_transfers(session: Session) -> None:
    _seed_bouzov(session)
    import_diary(session, _diary(), make_backup=False)
    incoming = _diary(
        visits=[
            _visit(
                note="Smazáno v PWA",
                updated_at="2026-08-10T12:00:00+02:00",
                deleted_at="2026-08-10T12:00:00+02:00",
            )
        ]
    )
    result = import_diary(session, incoming, make_backup=False)
    assert result.visits_updated == 1
    visit = session.scalar(select(Visit).where(Visit.public_id == VISIT_A))
    assert visit is not None
    assert visit.deleted_at == "2026-08-10T12:00:00+02:00"
    assert visit.note == "Smazáno v PWA"

    older = _diary(visits=[_visit(note="starší", updated_at="2026-08-09T10:00:00+02:00", deleted_at=None)])
    again = import_diary(session, older, make_backup=False)
    assert again.visits_unchanged == 1
    session.refresh(visit)
    assert visit.deleted_at == "2026-08-10T12:00:00+02:00"


def test_export_has_uuid_not_integer_pk(session: Session, tmp_path: Path) -> None:
    place = _seed_bouzov(session)
    import_diary(session, _diary(), make_backup=False)
    result = export_diary(session, tmp_path / "diary.json")
    validate_diary(result.diary)
    visit = result.diary["visits"][0]
    assert visit["id"] == VISIT_A
    assert visit["place_id"] == BOUZOV_ID
    assert result.diary["schema_version"] == 2
    assert result.diary["trips"] == []
    assert isinstance(visit["id"], str)
    raw = json.dumps(result.diary)
    db_visit = session.scalar(select(Visit).where(Visit.public_id == VISIT_A))
    assert db_visit is not None
    assert f'"id": {db_visit.id}' not in raw
    assert f'"id": {place.id}' not in raw
    assert "public_id" not in visit
    assert "place_public_id" not in visit


def test_merge_places_moves_visits_keeps_visit_public_id(session: Session) -> None:
    winner = create_place(session, _place_input(name="Bouzov"))
    loser = create_place(session, _place_input(name="Hrad Bouzov"))
    session.add(
        Visit(
            public_id=VISIT_A,
            place_id=loser.id,
            place_public_id=loser.public_id,
            visited_at="2026-08-09",
            rating=5,
            people_json='["Petr"]',
            created_at="2026-08-09T18:20:00+02:00",
            updated_at="2026-08-09T18:20:00+02:00",
        )
    )
    session.commit()
    winner_pid = winner.public_id
    merge_places(session, winner, loser)
    visit = session.scalar(select(Visit).where(Visit.public_id == VISIT_A))
    assert visit is not None
    assert visit.public_id == VISIT_A
    assert visit.place_id == winner.id
    assert visit.place_public_id == winner_pid


def test_dashboard_and_filters_use_visits(session: Session) -> None:
    bouzov = _seed_bouzov(session)
    other = create_place(session, _place_input(name="Karlštejn", municipality="Karlštejn"))
    import_diary(
        session,
        _diary(
            visits=[_visit()],
            states=[_state(want_to_visit=True, favorite=False)],
        ),
        make_backup=False,
    )
    stats = dashboard_stats(session)
    assert stats.visit_count == 1
    assert stats.unique_visited_places == 1
    assert stats.want_to_visit == 1
    assert stats.favorite == 0

    visited = list_places(session, PlaceFilters(journal="visited"))
    assert [row.public_id for row in visited.places] == [bouzov.public_id]
    not_visited = list_places(session, PlaceFilters(journal="not_visited"))
    assert [row.public_id for row in not_visited.places] == [other.public_id]
    want = list_places(session, PlaceFilters(journal="want_to_visit"))
    assert [row.public_id for row in want.places] == [bouzov.public_id]
    fav = list_places(session, PlaceFilters(journal="favorite"))
    assert fav.places == []


def test_ui_import_export_diary_and_visits_on_detail(client) -> None:
    created = client.post(
        "/places",
        data={
            "name": "Bouzov",
            "condition": "PRESERVED",
            "visitability": "REGULAR",
            "quality_status": "VERIFIED",
            "country": "CZ",
            "type_codes": ["CASTLE"],
        },
        follow_redirects=False,
    )
    assert created.status_code == 303
    public_id = created.headers["location"].split("/")[2].split("?")[0]

    diary = _diary(
        visits=[_visit(place_id=public_id), _visit(id=VISIT_B, place_id=public_id, visited_at="2026-08-11")],
        states=[_state(place_id=public_id)],
    )
    payload = json.dumps(diary).encode("utf-8")
    imported = client.post("/diary/import", files={"file": ("diary.json", payload, "application/json")})
    assert imported.status_code == 200
    assert "návštěvy nové: 2" in imported.text

    again = client.post("/diary/import", files={"file": ("diary.json", payload, "application/json")})
    assert again.status_code == 200
    assert "návštěvy nové: 0" in again.text

    dashboard = client.get("/")
    assert dashboard.status_code == 200
    assert "Počet návštěv" in dashboard.text
    assert "<strong>2</strong>" in dashboard.text

    detail = client.get(f"/places/{public_id}")
    assert "2026-08-09" in detail.text
    assert "2026-08-11" in detail.text
    assert "Jana, Petr" in detail.text

    listing = client.get("/places?journal=visited")
    assert "Bouzov" in listing.text

    exported = client.post("/diary/export")
    assert exported.status_code == 200
    assert "diary.json" in exported.headers.get("content-disposition", "")
    data = exported.json()
    validate_diary(data)
    assert len(data["visits"]) == 2
    assert get_default_diary_path().is_file()


def test_cli_export_import_diary(client, tmp_path: Path) -> None:
    client.post(
        "/places",
        data={
            "name": "Bouzov",
            "condition": "PRESERVED",
            "visitability": "REGULAR",
            "quality_status": "VERIFIED",
            "country": "CZ",
            "type_codes": ["CASTLE"],
        },
    )
    from app.cli import main
    from app.db.session import get_session

    session = get_session()
    try:
        place = session.scalar(select(Place).where(Place.name == "Bouzov"))
        assert place is not None
        public_id = place.public_id
    finally:
        session.close()

    source = tmp_path / "in.json"
    source.write_text(
        json.dumps(_diary(visits=[_visit(place_id=public_id)], states=[_state(place_id=public_id)])),
        encoding="utf-8",
    )
    assert main(["import-diary", str(source)]) == 0
    out = tmp_path / "out.json"
    assert main(["export-diary", "-o", str(out)]) == 0
    loaded = load_and_validate_diary(out)
    assert loaded["visits"][0]["place_id"] == public_id
    assert loaded["exported_from"] == "pc"


def test_add_visit_gets_new_uuid_two_same_day_remain_two(session: Session) -> None:
    place = _seed_bouzov(session)
    first = add_visit(session, place, visited_at="2026-08-09", rating=5, people="Jana, Petr", note="A")
    second = add_visit(session, place, visited_at="2026-08-09", rating=4, people="Petr", note="B")
    assert first.public_id != second.public_id
    assert first.place_id == place.id
    assert first.place_public_id == BOUZOV_ID
    assert first.people == ["Jana", "Petr"]
    assert second.people == ["Petr"]
    assert first.deleted_at is None
    rows = list_visits_for_place(session, place)
    assert len(rows) == 2
    payload = visit_to_json(first)
    assert payload["id"] == first.public_id
    assert "public_id" not in payload
    assert isinstance(payload["id"], str)


def test_parse_people_splits_and_dedupes() -> None:
    assert parse_people("Jana, Petr; Jana\nAnna") == ["Jana", "Petr", "Anna"]
    assert parse_people("  ") == []


def test_add_visit_rejects_invalid_rating(session: Session) -> None:
    place = _seed_bouzov(session)
    with pytest.raises(VisitInputError, match="1–5"):
        add_visit(session, place, visited_at="2026-08-09", rating=9, people="", note=None)
    assert session.scalar(select(func.count()).select_from(Visit)) == 0


def test_soft_delete_hides_visit_and_transfers_on_export(session: Session, tmp_path: Path) -> None:
    place = _seed_bouzov(session)
    visit = add_visit(session, place, visited_at="2026-08-09", rating=5, people="Petr", note="ok")
    public_id = visit.public_id
    soft_delete_visit(session, visit)
    session.refresh(visit)
    assert visit.deleted_at is not None
    assert list_visits_for_place(session, place) == []
    result = export_diary(session, tmp_path / "diary.json")
    exported = next(item for item in result.diary["visits"] if item["id"] == public_id)
    assert exported["deleted_at"] == visit.deleted_at


def test_save_journal_state_does_not_change_place(session: Session) -> None:
    place = _seed_bouzov(session)
    name = place.name
    save_journal_state(session, place, want_to_visit=True, favorite=True, personal_note="  chci znovu  ")
    session.refresh(place)
    assert place.name == name
    assert place.journal_state is not None
    assert place.journal_state.want_to_visit == 1
    assert place.journal_state.favorite == 1
    assert place.journal_state.personal_note == "chci znovu"
    assert place.journal_state.deleted_at is None


def test_ui_add_delete_visit_and_journal_flags(client) -> None:
    created = client.post(
        "/places",
        data={
            "name": "Bouzov",
            "condition": "PRESERVED",
            "visitability": "REGULAR",
            "quality_status": "VERIFIED",
            "country": "CZ",
            "type_codes": ["CASTLE"],
        },
        follow_redirects=False,
    )
    public_id = created.headers["location"].split("/")[2].split("?")[0]

    added = client.post(
        f"/places/{public_id}/visits",
        data={
            "visited_at": "2026-08-09",
            "rating": "5",
            "people": "Jana, Petr",
            "note": "Výborná prohlídka.",
        },
        follow_redirects=False,
    )
    assert added.status_code == 303
    assert added.headers["location"] == f"/places/{public_id}?notice=visit_added"

    again = client.post(
        f"/places/{public_id}/visits",
        data={
            "visited_at": "2026-08-09",
            "rating": "4",
            "people": "Petr",
            "note": "Druhá návštěva.",
        },
        follow_redirects=False,
    )
    assert again.status_code == 303

    detail = client.get(f"/places/{public_id}")
    assert detail.status_code == 200
    assert "Uložit návštěvu" in detail.text
    assert "Výborná prohlídka." in detail.text
    assert "Druhá návštěva." in detail.text
    assert "Jana, Petr" in detail.text

    dashboard = client.get("/")
    assert "<strong>2</strong>" in dashboard.text

    listing = client.get("/places?journal=visited")
    assert "Bouzov" in listing.text

    bad = client.post(
        f"/places/{public_id}/visits",
        data={"visited_at": "2026-08-09", "rating": "9", "people": "", "note": ""},
    )
    assert bad.status_code == 400
    assert "Hodnocení musí být 1–5." in bad.text

    flags = client.post(
        f"/places/{public_id}/journal",
        data={"want_to_visit": "1", "favorite": "1", "personal_note": "chci znovu"},
        follow_redirects=False,
    )
    assert flags.status_code == 303
    want = client.get("/places?journal=want_to_visit")
    assert "Bouzov" in want.text
    fav = client.get("/places?journal=favorite")
    assert "Bouzov" in fav.text
    detail_flags = client.get(f"/places/{public_id}")
    assert "chci znovu" in detail_flags.text
    assert 'name="want_to_visit"' in detail_flags.text
    assert "checked" in detail_flags.text

    from app.db.session import get_session

    db = get_session()
    try:
        rows = list(
            db.scalars(select(Visit).where(Visit.place_public_id == public_id, Visit.deleted_at.is_(None)))
        )
        assert len(rows) == 2
        visit_id = rows[0].public_id
        deleted_note = rows[0].note
    finally:
        db.close()

    deleted = client.post(
        f"/places/{public_id}/visits/{visit_id}/delete",
        follow_redirects=False,
    )
    assert deleted.status_code == 303
    after = client.get(f"/places/{public_id}")
    assert deleted_note not in after.text
    remaining = "Výborná prohlídka." if deleted_note != "Výborná prohlídka." else "Druhá návštěva."
    assert remaining in after.text

    exported = client.post("/diary/export")
    data = exported.json()
    validate_diary(data)
    assert len(data["visits"]) == 2
    assert sum(1 for item in data["visits"] if item["deleted_at"]) == 1
    assert data["exported_from"] == "pc"


def test_visit_to_json_never_includes_integer_id(session: Session) -> None:
    _seed_bouzov(session)
    import_diary(session, _diary(), make_backup=False)
    visit = session.scalar(select(Visit).where(Visit.public_id == VISIT_A))
    assert visit is not None
    payload = visit_to_json(visit)
    assert set(payload) == {
        "id",
        "place_id",
        "visited_at",
        "rating",
        "people",
        "note",
        "trip_id",
        "created_at",
        "updated_at",
        "deleted_at",
    }
    assert payload["id"] == VISIT_A


def test_repeated_trip_import_creates_zero_duplicates(session: Session) -> None:
    _seed_bouzov(session)
    data = _diary(trips=[_trip()])
    first = import_diary(session, data, make_backup=False)
    second = import_diary(session, data, make_backup=False)
    assert first.trips_inserted == 1
    assert second.trips_inserted == 0
    assert second.trips_updated == 0
    assert session.scalar(select(func.count()).select_from(Trip)) == 1
    assert session.scalar(select(func.count()).select_from(TripStop)) == 1


def test_unknown_place_id_in_trip_stop_does_not_create_place(session: Session) -> None:
    _seed_bouzov(session)
    before = session.scalar(select(func.count()).select_from(Place)) or 0
    result = import_diary(
        session,
        _diary(trips=[_trip(stops=[{"place_id": UNKNOWN_PLACE, "sort_order": 0, "note": None}])]),
        make_backup=False,
    )
    assert result.trips_inserted == 1
    assert UNKNOWN_PLACE in result.unknown_place_ids
    assert session.scalar(select(func.count()).select_from(Place)) == before
    trip = session.scalar(select(Trip).where(Trip.public_id == TRIP_A))
    assert trip is not None
    assert len(trip.stops) == 1
    assert trip.stops[0].place_public_id == UNKNOWN_PLACE
    assert trip.stops[0].place_id is None


def test_schema_version_1_import_does_not_wipe_trips(session: Session) -> None:
    _seed_bouzov(session)
    import_diary(session, _diary(trips=[_trip()]), make_backup=False)
    again = import_diary(session, _diary(), make_backup=False)
    assert again.trips_inserted == 0
    trip = session.scalar(select(Trip).where(Trip.public_id == TRIP_A))
    assert trip is not None
    assert trip.deleted_at is None
    assert trip.name == "Olomoucko"


def test_deleted_trip_is_not_reinserted_from_older_file(session: Session) -> None:
    _seed_bouzov(session)
    import_diary(
        session,
        _diary(
            trips=[
                _trip(
                    updated_at="2026-08-17T10:00:00+02:00",
                    deleted_at="2026-08-17T10:00:00+02:00",
                )
            ]
        ),
        make_backup=False,
    )
    older = import_diary(
        session,
        _diary(trips=[_trip(updated_at="2026-08-16T10:00:00+02:00", deleted_at=None)]),
        make_backup=False,
    )
    assert older.trips_updated == 0
    trip = session.scalar(select(Trip).where(Trip.public_id == TRIP_A))
    assert trip is not None
    assert trip.deleted_at == "2026-08-17T10:00:00+02:00"


def test_export_diary_is_schema_version_2_with_trips(session: Session, tmp_path: Path) -> None:
    _seed_bouzov(session)
    import_diary(session, _diary(trips=[_trip()]), make_backup=False)
    result = export_diary(session, tmp_path / "diary.json")
    validate_diary(result.diary)
    assert result.diary["schema_version"] == 2
    assert result.diary["trips"][0]["id"] == TRIP_A
    assert result.diary["trips"][0]["stops"][0]["place_id"] == BOUZOV_ID
    raw = json.dumps(result.diary)
    db_trip = session.scalar(select(Trip).where(Trip.public_id == TRIP_A))
    assert db_trip is not None
    assert f'"id": {db_trip.id}' not in raw
    assert "public_id" not in result.diary["trips"][0]


def test_merge_places_repoints_trip_stops(session: Session) -> None:
    winner = create_place(session, _place_input(name="Bouzov"))
    loser = create_place(session, _place_input(name="Hrad Bouzov"))
    import_diary(
        session,
        _diary(trips=[_trip(stops=[{"place_id": loser.public_id, "sort_order": 0, "note": None}])]),
        make_backup=False,
    )
    winner_pid = winner.public_id
    merge_places(session, winner, loser)
    trip = session.scalar(select(Trip).where(Trip.public_id == TRIP_A))
    assert trip is not None
    assert trip.stops[0].place_id == winner.id
    assert trip.stops[0].place_public_id == winner_pid
