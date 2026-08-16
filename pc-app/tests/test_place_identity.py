from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.db.enums import codes, format_types
from app.db.migrate import run_migrations
from app.db.models import Place, PlaceType
from app.db.session import create_engine_for
from app.ids import new_public_id
from app.services.catalog_schema import load_catalog_schema


def test_migration_creates_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "empty.sqlite3"
    run_migrations(db_path)
    engine = create_engine_for(db_path)
    names = set(inspect(engine).get_table_names())
    engine.dispose()
    assert {"places", "place_types", "place_place_types", "app_meta", "alembic_version"} <= names


def test_insert_place_gets_uuid7_public_id(session: Session) -> None:
    place = Place(name="Bouzov")
    session.add(place)
    session.commit()
    session.refresh(place)
    assert place.public_id
    assert place.public_id != new_public_id()
    from uuid import UUID

    assert UUID(place.public_id).version == 7


def test_second_insert_gets_different_public_id(session: Session) -> None:
    a = Place(name="Bouzov")
    b = Place(name="Karlštejn")
    session.add_all([a, b])
    session.commit()
    assert a.public_id != b.public_id


def test_update_name_does_not_change_public_id(session: Session) -> None:
    place = Place(name="Bouzov")
    session.add(place)
    session.commit()
    original = place.public_id
    place.name = "Hrad Bouzov"
    session.commit()
    session.refresh(place)
    assert place.public_id == original
    assert place.name == "Hrad Bouzov"


def test_public_id_cannot_be_reassigned(session: Session) -> None:
    place = Place(name="Bouzov")
    session.add(place)
    session.commit()
    with pytest.raises(ValueError, match="immutable"):
        place.public_id = new_public_id()


def test_seed_contains_expected_types(session: Session) -> None:
    codes_in_db = set(session.scalars(select(PlaceType.code)).all())
    assert codes_in_db == codes("place_types")
    assert "CASTLE_CHATEAU" not in codes_in_db


def test_catalog_schema_enums_match_enums_json() -> None:
    defs = load_catalog_schema()["$defs"]
    assert set(defs["placeTypeCode"]["enum"]) == codes("place_types")
    assert set(defs["conditionCode"]["enum"]) == codes("condition")
    assert set(defs["visitabilityCode"]["enum"]) == codes("visitability")
    assert set(defs["heritageStatusCode"]["enum"]) == codes("heritage_status")


def test_format_types_matches_pwa() -> None:
    assert format_types(["CASTLE", "CHATEAU"]) == "Hrad a zámek"
    assert format_types([]) == "Bez typu"
    assert format_types(["CASTLE"]) == "Hrad"
    assert format_types(["LOOKOUT_TOWER"]) == "Rozhledna"
    assert format_types(["ZOO"]) == "Zoo"
    assert format_types(["CAVE"]) == "Jeskyně"


def test_seed_updates_stale_type_labels(session: Session) -> None:
    from app.db.seed import seed_place_types

    row = session.scalar(select(PlaceType).where(PlaceType.code == "CASTLE"))
    assert row is not None
    row.name_cs = "Stale"
    row.sort_order = 99
    session.commit()
    seed_place_types(session)
    session.refresh(row)
    assert row.name_cs == "Hrad"
    assert row.sort_order == 1
