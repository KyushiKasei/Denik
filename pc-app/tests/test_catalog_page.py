from pathlib import Path

from fastapi.testclient import TestClient

from app.db.session import reset_engine


def test_catalog_page_shows_zero_places(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PAMATKY_DATA_DIR", str(tmp_path))
    reset_engine()
    from app.main import app

    with TestClient(app) as client:
        response = client.get("/")
    reset_engine()
    assert response.status_code == 200
    assert "Aktivních míst" in response.text
    assert "<strong>0</strong>" in response.text
