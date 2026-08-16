from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.db.migrate import run_migrations
from app.db.seed import seed_place_types
from app.db.session import create_engine_for, make_session_factory, reset_engine


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


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("PAMATKY_DATA_DIR", str(tmp_path))
    reset_engine()
    from app.main import app
    from app.services.import_job import reset_job_state

    reset_job_state()
    with TestClient(app) as test_client:
        yield test_client
    reset_job_state()
    reset_engine()
