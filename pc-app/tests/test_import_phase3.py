from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import func, inspect, select
from sqlalchemy.orm import Session

from app.db.migrate import run_migrations
from app.db.models import (
    ImportFieldChange,
    ImportReview,
    ImportRun,
    Place,
    PlaceFieldOverride,
    PlaceSource,
)
from app.db.session import create_engine_for
from app.importers.base import CanonicalRecord
from app.importers.fixture import DEFAULT_FIXTURE, load_fixture
from app.services.apply_import import (
    ImportApplyError,
    apply_import,
    preview_import,
    reprocess_open_reviews,
    resolve_create_new,
    resolve_ignore,
    resolve_merge,
)
from app.services.matching import (
    LEVEL_A,
    LEVEL_B,
    LEVEL_C,
    LEVEL_D,
    distance_m,
    match_record,
    name_similarity,
    normalize_name,
)
from app.services.places import PlaceInput, update_place
from app.services.import_progress import data_dir_for_session, read_progress

UPDATE_FIXTURE = DEFAULT_FIXTURE.parent / "small_dataset_update.json"

PHASE3_TABLES = {
    "place_sources",
    "place_source_values",
    "place_field_overrides",
    "place_photos",
    "import_runs",
    "import_reviews",
    "import_review_candidates",
    "import_field_changes",
}


def _apply(session: Session, records: list[CanonicalRecord], source_type: str = "wikidata"):
    return apply_import(session, records, source_type, make_backup=True)


def _record(**overrides) -> CanonicalRecord:
    data = {
        "source_type": "wikidata",
        "external_id": "Q-test",
        "external_ids": {"wikidata": "Q-test"},
        "name": "Test",
        "types": ["CASTLE"],
        "latitude": 50.0,
        "longitude": 14.0,
        "municipality": "Praha",
        "district": "Praha",
        "fetched_at": "2026-08-14T20:00:00+02:00",
    }
    data.update(overrides)
    if "external_id" in overrides and "external_ids" not in overrides:
        data["external_ids"] = {data["source_type"]: overrides["external_id"]}
    return CanonicalRecord.from_dict(data)


def test_phase3_migration_creates_import_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "empty.sqlite3"
    run_migrations(db_path)
    engine = create_engine_for(db_path)
    names = set(inspect(engine).get_table_names())
    engine.dispose()
    assert PHASE3_TABLES <= names


def test_repeated_fixture_keeps_public_id(session: Session) -> None:
    source_type, records = load_fixture(DEFAULT_FIXTURE)
    first = _apply(session, records, source_type)
    assert first.records_created == 3
    assert first.counts_ok()
    ids = {row.public_id for row in session.scalars(select(Place)).all()}
    assert len(ids) == 3

    second = _apply(session, records, source_type)
    assert second.records_created == 0
    assert second.records_review == 0
    assert second.records_updated + second.records_unchanged == 3
    assert second.counts_ok()
    again = {row.public_id for row in session.scalars(select(Place)).all()}
    assert again == ids


def test_new_place_gets_new_id(session: Session) -> None:
    source_type, records = load_fixture(DEFAULT_FIXTURE)
    _apply(session, records, source_type)
    original = {row.public_id for row in session.scalars(select(Place)).all()}
    extra = _record(external_id="Q747444", name="Křivoklát", municipality="Křivoklát", district="Rakovník",
                    latitude=50.0378, longitude=13.8725)
    result = _apply(session, [extra], "wikidata")
    assert result.records_created == 1
    now = {row.public_id for row in session.scalars(select(Place)).all()}
    assert len(now - original) == 1


def test_same_external_id_never_creates_second_place(session: Session) -> None:
    first = _record(external_id="Q122922", name="Bouzov", municipality="Bouzov", district="Olomouc",
                    latitude=49.704, longitude=16.891)
    _apply(session, [first])
    second = _record(external_id="Q122922", name="Hrad Bouzov úplně jinak", municipality="Jinde",
                     latitude=48.0, longitude=12.0)
    result = _apply(session, [second])
    assert result.records_created == 0
    places = list(session.scalars(select(Place)).all())
    assert len(places) == 1
    assert places[0].public_id == result.outcomes[0].public_id
    sources = list(session.scalars(select(PlaceSource).where(PlaceSource.external_id == "Q122922")).all())
    assert len(sources) == 1


def test_match_via_wikidata_id(session: Session) -> None:
    _apply(session, [_record(external_id="Q214651", name="Karlštejn", municipality="Karlštejn",
                             district="Beroun", latitude=49.93944, longitude=14.18806)])
    place = session.scalar(select(Place).where(Place.name == "Karlštejn"))
    assert place is not None
    public_id = place.public_id
    incoming = _record(external_id="Q214651", name="Státní hrad Karlštejn", municipality="Karlštejn",
                       district="Beroun", latitude=49.93944, longitude=14.18806)
    decision = match_record(session, incoming)
    assert decision.level == LEVEL_A
    result = _apply(session, [incoming])
    assert result.records_created == 0
    session.refresh(place)
    assert place.public_id == public_id
    assert session.scalar(select(func.count()).select_from(Place)) == 1


def test_match_via_pamatkovy_katalog_id(session: Session) -> None:
    seeded = _record(
        external_id="Q122922",
        external_ids={"wikidata": "Q122922", "pamatkovy_katalog": "1000004417"},
        name="Bouzov",
        municipality="Bouzov",
        district="Olomouc",
        latitude=49.704,
        longitude=16.891,
    )
    _apply(session, [seeded])
    place = session.scalar(select(Place))
    assert place is not None
    public_id = place.public_id
    from_catalog = CanonicalRecord.from_dict(
        {
            "source_type": "pamatkovy_katalog",
            "external_id": "1000004417",
            "external_ids": {"pamatkovy_katalog": "1000004417"},
            "name": "Bouzov",
            "types": ["CASTLE"],
            "municipality": "Bouzov",
            "district": "Olomouc",
            "latitude": 49.704,
            "longitude": 16.891,
            "fetched_at": "2026-08-14T21:00:00+02:00",
        }
    )
    decision = match_record(session, from_catalog)
    assert decision.level == LEVEL_A
    result = apply_import(session, [from_catalog], "pamatkovy_katalog", make_backup=True)
    assert result.records_created == 0
    session.refresh(place)
    assert place.public_id == public_id
    assert session.scalar(select(func.count()).select_from(Place)) == 1


def test_probable_match_gps_and_name_threshold_b(session: Session) -> None:
    existing = Place(
        name="Bouzov",
        municipality="Bouzov",
        district="Olomouc",
        latitude=49.704,
        longitude=16.891,
        condition="UNKNOWN",
        visitability="UNKNOWN",
    )
    session.add(existing)
    session.commit()
    public_id = existing.public_id
    incoming = _record(
        source_type="wikidata",
        external_id="Q-new-bouzov",
        name="Hrad Bouzov",
        municipality="Bouzov",
        district="Olomouc",
        latitude=49.70445,
        longitude=16.891,
        types=["CASTLE"],
    )
    dist = distance_m(49.704, 16.891, 49.70445, 16.891)
    assert dist is not None and dist <= 100
    assert normalize_name("Hrad Bouzov") == normalize_name("Bouzov")
    decision = match_record(session, incoming)
    assert decision.level == LEVEL_B
    result = _apply(session, [incoming])
    assert result.records_created == 0
    assert result.records_updated == 1
    session.refresh(existing)
    assert existing.public_id == public_id
    source = session.scalar(select(PlaceSource).where(PlaceSource.external_id == "Q-new-bouzov"))
    assert source is not None
    assert source.place_id == existing.id


def test_unclear_match_goes_to_review_and_does_not_create_place(session: Session) -> None:
    _apply(session, [_record(external_id="Q214651", name="Karlštejn", municipality="Karlštejn",
                             district="Beroun", latitude=49.93944, longitude=14.18806)])
    incoming = _record(
        external_id="Q-unclear-karlstein",
        name="Karlstein",
        municipality="Karlštejn",
        district="Beroun",
        latitude=49.94124,
        longitude=14.18806,
        types=["CASTLE"],
    )
    sim = name_similarity("Karlštejn", "Karlstein")
    dist = distance_m(49.93944, 14.18806, 49.94124, 14.18806)
    assert 0.75 <= sim < 0.90
    assert dist is not None and 100 < dist <= 400
    decision = match_record(session, incoming)
    assert decision.level == LEVEL_C
    result = _apply(session, [incoming])
    assert result.records_created == 0
    assert result.records_review == 1
    assert session.scalar(select(func.count()).select_from(Place)) == 1
    review = session.scalar(select(ImportReview).where(ImportReview.status == "open"))
    assert review is not None
    assert review.external_id == "Q-unclear-karlstein"
    assert session.scalar(select(PlaceSource).where(PlaceSource.external_id == "Q-unclear-karlstein")) is None


def test_b4_identical_name_missing_municipality_within_300m_merges(session: Session) -> None:
    """OSM centroid ~135 m od bodu katalogu, obec na OSM chybí — stejný hrad, připoj zdroj."""
    _apply(
        session,
        [
            _record(
                external_id="Q-pernstejn",
                name="Pernštejn",
                municipality="Nedvědice",
                district="Brno-venkov",
                latitude=49.4508333333,
                longitude=16.3188888888,
                types=["CASTLE"],
            )
        ],
    )
    place = session.scalar(select(Place))
    assert place is not None
    public_id = place.public_id
    incoming = CanonicalRecord.from_dict(
        {
            "source_type": "osm",
            "external_id": "relation/10843713",
            "external_ids": {"osm": "relation/10843713"},
            "name": "Pernštejn",
            "types": ["CASTLE"],
            "latitude": 49.4513905,
            "longitude": 16.3172329,
            "fetched_at": "2026-08-16T21:00:00+02:00",
        }
    )
    dist = distance_m(49.4508333333, 16.3188888888, 49.4513905, 16.3172329)
    assert dist is not None and 100 < dist <= 300
    decision = match_record(session, incoming)
    assert decision.level == LEVEL_B
    assert "B4" in decision.reason
    result = apply_import(session, [incoming], "osm", make_backup=True)
    assert result.records_created == 0
    assert result.records_updated == 1
    assert result.records_review == 0
    session.refresh(place)
    assert place.public_id == public_id
    source = session.scalar(
        select(PlaceSource).where(
            PlaceSource.source_type == "osm",
            PlaceSource.external_id == "relation/10843713",
        )
    )
    assert source is not None
    assert source.place_id == place.id


def test_b4_generic_castle_name_stays_in_review(session: Session) -> None:
    _apply(
        session,
        [
            _record(
                external_id="Q-generic-1",
                name="zámek",
                municipality="Ptení",
                latitude=49.51,
                longitude=16.96,
                types=["CHATEAU"],
            )
        ],
    )
    incoming = CanonicalRecord.from_dict(
        {
            "source_type": "osm",
            "external_id": "way/1",
            "external_ids": {"osm": "way/1"},
            "name": "zámek",
            "types": ["CHATEAU"],
            "latitude": 49.511,
            "longitude": 16.96,
            "fetched_at": "2026-08-16T21:00:00+02:00",
        }
    )
    decision = match_record(session, incoming)
    assert decision.level == LEVEL_C


def test_reprocess_open_reviews_merges_b4(session: Session) -> None:
    _apply(
        session,
        [
            _record(
                external_id="Q-pernstejn",
                name="Pernštejn",
                municipality="Nedvědice",
                latitude=49.4508333333,
                longitude=16.3188888888,
                types=["CASTLE"],
            )
        ],
    )
    leftover = CanonicalRecord.from_dict(
        {
            "source_type": "osm",
            "external_id": "relation/10843713",
            "external_ids": {"osm": "relation/10843713"},
            "name": "Pernštejn",
            "types": ["CASTLE"],
            "latitude": 49.4513905,
            "longitude": 16.3172329,
            "fetched_at": "2026-08-16T21:00:00+02:00",
        }
    )
    run = session.scalar(select(ImportRun).order_by(ImportRun.id.desc()))
    assert run is not None
    session.add(
        ImportReview(
            import_run_id=run.id,
            source_type="osm",
            external_id="relation/10843713",
            raw_data=json.dumps(leftover.to_dict(), ensure_ascii=False),
            status="open",
            match_reason="C1 distance=134.8m similarity=1.000",
        )
    )
    session.commit()
    result = reprocess_open_reviews(session, make_backup=True)
    assert result.records_updated + result.records_unchanged == 1
    assert result.records_review == 0
    assert session.scalar(select(func.count()).select_from(ImportReview).where(ImportReview.status == "open")) == 0
    source = session.scalar(
        select(PlaceSource).where(PlaceSource.external_id == "relation/10843713")
    )
    assert source is not None


def test_palace_matches_chateau_within_100m(session: Session) -> None:
    _apply(
        session,
        [
            _record(
                external_id="Q-oldrisov",
                name="Zámek Oldřišov",
                municipality="Oldřišov",
                latitude=49.95,
                longitude=17.96,
                types=["CHATEAU"],
            )
        ],
    )
    incoming = CanonicalRecord.from_dict(
        {
            "source_type": "osm",
            "external_id": "way/53064118",
            "external_ids": {"osm": "way/53064118"},
            "name": "Zámek Oldřišov",
            "types": ["PALACE"],
            "latitude": 49.95004,
            "longitude": 17.96,
            "fetched_at": "2026-08-16T22:00:00+02:00",
        }
    )
    decision = match_record(session, incoming)
    assert decision.level == LEVEL_B


def test_c2_same_municipality_beyond_gps_radius_goes_to_review(session: Session) -> None:
    _apply(
        session,
        [
            _record(
                external_id="Q-rohozec",
                name="Hrubý Rohozec",
                municipality="Turnov",
                latitude=50.595,
                longitude=15.157,
            )
        ],
    )
    incoming = _record(
        external_id="Q-rohozec-far",
        name="Hruby Rohozec",
        municipality="Turnov",
        latitude=50.625,
        longitude=15.157,
        types=["CHATEAU"],
    )
    sim = name_similarity("Hrubý Rohozec", "Hruby Rohozec")
    dist = distance_m(50.595, 15.157, 50.625, 15.157)
    assert sim >= 0.82
    assert dist is not None and dist > 400
    decision = match_record(session, incoming)
    assert decision.level == LEVEL_C
    assert "C2" in decision.reason


def test_manual_name_fix_survives_second_import(session: Session) -> None:
    source_type, records = load_fixture(DEFAULT_FIXTURE)
    _apply(session, records, source_type)
    place = session.scalar(select(Place).where(Place.name == "Bouzov"))
    assert place is not None
    public_id = place.public_id
    data = PlaceInput.from_place(place)
    data.name = "Hrad Bouzov"
    update_place(session, place, data)
    session.refresh(place)
    assert place.name == "Hrad Bouzov"
    override = session.get(PlaceFieldOverride, (place.id, "name"))
    assert override is not None

    _apply(session, records, source_type)
    session.refresh(place)
    assert place.public_id == public_id
    assert place.name == "Hrad Bouzov"
    change = session.scalar(
        select(ImportFieldChange).where(
            ImportFieldChange.place_id == place.id,
            ImportFieldChange.field_name == "name",
            ImportFieldChange.status == "open",
        )
    )
    assert change is not None


def test_backup_created_before_apply(session: Session) -> None:
    source_type, records = load_fixture(DEFAULT_FIXTURE)
    result = _apply(session, records, source_type)
    assert result.backup_path
    path = Path(result.backup_path)
    assert path.is_file()
    assert "before-" in path.name
    assert path.stat().st_size > 0
    progress = read_progress(data_dir_for_session(session))
    assert progress.status == "applied"
    assert progress.current == progress.total == result.records_received
    assert "Import zapsán" in progress.message


def test_fatal_apply_error_rolls_back(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    source_type, records = load_fixture(DEFAULT_FIXTURE)
    first = _apply(session, records[:1], source_type)
    assert first.records_created == 1
    kept = session.scalar(select(Place)).public_id

    import app.services.apply_import as apply_mod

    original = apply_mod.create_place_from_record
    calls = {"n": 0}

    def boom(session_arg, record, run):
        calls["n"] += 1
        if calls["n"] >= 2:
            raise RuntimeError("fatal test error")
        return original(session_arg, record, run)

    monkeypatch.setattr(apply_mod, "create_place_from_record", boom)
    with pytest.raises(ImportApplyError, match="fatal test error"):
        apply_import(session, records[1:], source_type, make_backup=True)

    places = list(session.scalars(select(Place)).all())
    assert len(places) == 1
    assert places[0].public_id == kept


def test_fixture_update_one_created_one_review_zero_duplicates(session: Session) -> None:
    source_type, first_records = load_fixture(DEFAULT_FIXTURE)
    first = _apply(session, first_records, source_type)
    original_ids = {row.public_id for row in session.scalars(select(Place)).all()}
    assert first.records_created == 3

    _, update_records = load_fixture(UPDATE_FIXTURE)
    second = _apply(session, update_records, source_type)
    assert second.records_created == 1
    assert second.records_review == 1
    assert second.records_failed == 0
    assert second.counts_ok()
    places = list(session.scalars(select(Place)).all())
    assert len(places) == 4
    current_ids = {row.public_id for row in places}
    assert original_ids <= current_ids
    qids = [
        row.external_id
        for row in session.scalars(select(PlaceSource).where(PlaceSource.source_type == "wikidata")).all()
    ]
    assert len(qids) == len(set(qids))
    assert session.scalar(select(func.count()).select_from(ImportReview).where(ImportReview.status == "open")) == 1


def test_preview_does_not_write_places(session: Session) -> None:
    source_type, records = load_fixture(DEFAULT_FIXTURE)
    preview = preview_import(session, records, source_type)
    assert preview.status == "preview"
    assert preview.records_created == 3
    assert session.scalar(select(func.count()).select_from(Place)) == 0


def test_level_d_when_no_candidate(session: Session) -> None:
    incoming = _record(external_id="Q-unique", name="Osov", municipality="Osov", latitude=49.85, longitude=14.08)
    decision = match_record(session, incoming)
    assert decision.level == LEVEL_D


def test_review_merge_keeps_public_id_and_enables_level_a(session: Session) -> None:
    _apply(session, [_record(external_id="Q214651", name="Karlštejn", municipality="Karlštejn",
                             district="Beroun", latitude=49.93944, longitude=14.18806)])
    place = session.scalar(select(Place))
    assert place is not None
    public_id = place.public_id
    incoming = _record(
        external_id="Q-unclear-karlstein",
        name="Karlstein",
        municipality="Karlštejn",
        district="Beroun",
        latitude=49.94124,
        longitude=14.18806,
    )
    _apply(session, [incoming])
    review = session.scalar(select(ImportReview).where(ImportReview.status == "open"))
    assert review is not None
    resolve_merge(session, review, place)
    session.refresh(place)
    assert place.public_id == public_id
    source = session.scalar(select(PlaceSource).where(PlaceSource.external_id == "Q-unclear-karlstein"))
    assert source is not None
    assert source.place_id == place.id
    again = match_record(session, incoming)
    assert again.level == LEVEL_A


def test_review_ignore_skips_next_import(session: Session) -> None:
    _apply(session, [_record(external_id="Q214651", name="Karlštejn", municipality="Karlštejn",
                             district="Beroun", latitude=49.93944, longitude=14.18806)])
    incoming = _record(
        external_id="Q-unclear-karlstein",
        name="Karlstein",
        municipality="Karlštejn",
        district="Beroun",
        latitude=49.94124,
        longitude=14.18806,
    )
    _apply(session, [incoming])
    review = session.scalar(select(ImportReview).where(ImportReview.status == "open"))
    assert review is not None
    resolve_ignore(session, review)
    result = _apply(session, [incoming])
    assert result.records_ignored == 1
    assert result.records_created == 0
    assert session.scalar(select(func.count()).select_from(Place)) == 1


def test_review_create_new_assigns_new_public_id(session: Session) -> None:
    _apply(session, [_record(external_id="Q214651", name="Karlštejn", municipality="Karlštejn",
                             district="Beroun", latitude=49.93944, longitude=14.18806)])
    original = session.scalar(select(Place)).public_id
    incoming = _record(
        external_id="Q-unclear-karlstein",
        name="Karlstein",
        municipality="Karlštejn",
        district="Beroun",
        latitude=49.94124,
        longitude=14.18806,
    )
    _apply(session, [incoming])
    review = session.scalar(select(ImportReview).where(ImportReview.status == "open"))
    place = resolve_create_new(session, review)
    assert place.public_id != original
    assert session.scalar(select(func.count()).select_from(Place)) == 2


def test_identical_name_without_gps_creates_new_place(session: Session) -> None:
    """Holý název bez obce/GPS nestačí k review — zdroj s vlastním ID se založí."""
    manual = Place(name="Bouzov", condition="UNKNOWN", visitability="UNKNOWN")
    session.add(manual)
    session.commit()
    public_id = manual.public_id
    incoming = _record(
        external_id="Q122922",
        name="Hrad Bouzov",
        municipality="Bouzov",
        district="Olomouc",
        latitude=49.704,
        longitude=16.891,
        types=["CASTLE"],
    )
    decision = match_record(session, incoming)
    assert decision.level == LEVEL_D
    result = _apply(session, [incoming])
    assert result.records_created == 1
    assert result.records_review == 0
    assert session.scalar(select(func.count()).select_from(Place)) == 2
    session.refresh(manual)
    assert manual.public_id == public_id
    source = session.scalar(select(PlaceSource).where(PlaceSource.external_id == "Q122922"))
    assert source is not None
    assert source.place_id != manual.id


def test_reprocess_open_reviews_creates_generic_name_in_other_village(session: Session) -> None:
    _apply(
        session,
        [
            _record(
                external_id="Q-zamek-1",
                name="zámek",
                municipality="Ptení",
                district="Prostějov",
                latitude=49.51,
                longitude=16.96,
            )
        ],
    )
    leftover = _record(
        external_id="Q-zamek-2",
        name="zámek",
        municipality="Pavlovice u Přerova",
        district="Přerov",
        latitude=49.39,
        longitude=17.52,
    )
    run = session.scalar(select(ImportRun).order_by(ImportRun.id.desc()))
    assert run is not None
    session.add(
        ImportReview(
            import_run_id=run.id,
            source_type="wikidata",
            external_id="Q-zamek-2",
            raw_data=json.dumps(leftover.to_dict(), ensure_ascii=False),
            status="open",
            match_reason="C4 identical_name",
        )
    )
    session.commit()
    result = reprocess_open_reviews(session, make_backup=True)
    assert result.records_created == 1
    assert result.records_review == 0
    assert session.scalar(select(func.count()).select_from(Place)) == 2
    assert session.scalar(select(func.count()).select_from(ImportReview).where(ImportReview.status == "open")) == 0


def test_reprocess_keeps_same_municipality_review(session: Session) -> None:
    _apply(
        session,
        [
            _record(
                external_id="Q-zamek-1",
                name="zámek",
                municipality="Ptení",
                district="Prostějov",
                latitude=49.51,
                longitude=16.96,
            )
        ],
    )
    leftover = _record(
        external_id="Q-zamek-2",
        name="zámek",
        municipality="Ptení",
        district="Prostějov",
        latitude=None,
        longitude=None,
    )
    run = session.scalar(select(ImportRun).order_by(ImportRun.id.desc()))
    assert run is not None
    session.add(
        ImportReview(
            import_run_id=run.id,
            source_type="wikidata",
            external_id="Q-zamek-2",
            raw_data=json.dumps(leftover.to_dict(), ensure_ascii=False),
            status="open",
            match_reason="C4 identical_name",
        )
    )
    session.commit()
    result = reprocess_open_reviews(session, make_backup=True)
    assert result.records_created == 0
    assert result.records_review == 1
    assert session.scalar(select(func.count()).select_from(Place)) == 1


def test_merge_two_existing_places_keeps_winner_public_id(session: Session) -> None:
    from app.services.merge_places import merge_places

    winner = Place(name="Bouzov", municipality="Bouzov", condition="UNKNOWN", visitability="UNKNOWN")
    loser = Place(
        name="Hrad Bouzov",
        municipality="Bouzov",
        latitude=49.704,
        longitude=16.891,
        condition="PRESERVED",
        visitability="REGULAR",
    )
    session.add_all([winner, loser])
    session.flush()
    session.add(PlaceSource(place_id=loser.id, source_type="wikidata", external_id="Q122922", created_at="t", updated_at="t"))
    session.commit()
    winner_id = winner.public_id
    loser_id = loser.public_id

    merge_places(session, winner, loser)
    session.refresh(winner)
    session.refresh(loser)
    assert winner.public_id == winner_id
    assert loser.public_id == loser_id
    assert loser.archived_at is not None
    assert loser.merged_into_public_id == winner_id
    assert winner.latitude == 49.704
    source = session.scalar(select(PlaceSource).where(PlaceSource.external_id == "Q122922"))
    assert source is not None
    assert source.place_id == winner.id
    assert session.scalar(select(func.count()).select_from(Place)) == 2

