from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.db.migrate import run_migrations
from app.db.models import Place, PlaceType
from app.db.seed import seed_place_types
from app.db.session import create_engine_for, make_session_factory
from app.ids import new_public_id


EXPECTED_TYPE_CODES = {"CASTLE", "CHATEAU", "RUIN", "FORTRESS", "MANOR", "PALACE", "OTHER"}


@pytest.fixture
def session(tmp_path: Path) -> Session:
    db_path = tmp_path / "test.sqlite3"
    run_migrations(db_path)
    engine = create_engine_for(db_path)
    factory = make_session_factory(engine)
    db = factory()
    seed_place_types(db)
    yield db
    db.close()
    engine.dispose()


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
    codes = set(session.scalars(select(PlaceType.code)).all())
    assert codes == EXPECTED_TYPE_CODES
    assert "CASTLE_CHATEAU" not in codes
