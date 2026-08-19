from pathlib import Path

from fastapi.testclient import TestClient

from app.db.session import reset_engine


def test_dashboard_shows_zero_places(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PAMATKY_DATA_DIR", str(tmp_path))
    reset_engine()
    from app.main import app

    with TestClient(app) as client:
        response = client.get("/")
        css = client.get("/static/app.css")
    reset_engine()
    assert response.status_code == 200
    assert "Aktivních míst" in response.text
    assert "<strong>0</strong>" in response.text
    assert "Počet návštěv" in response.text
    assert "Pravděpodobné" in response.text
    assert "Vyřazené" in response.text
    assert "Chci navštívit" in response.text
    assert "Oblíbené" in response.text
    assert 'href="/places?quality_status=PROBABLE&worth=all"' in response.text
    assert 'href="/places?journal=favorite"' in response.text
    assert 'href="/visits"' in response.text
    assert 'href="/diary"' in response.text
    assert ">Deník</a>" in response.text
    assert "Kvalita katalogu" in response.text
    assert "<h2>Deník</h2>" in response.text
    nav = response.text.split("<main", 1)[0]
    assert 'href="/places/new"' not in nav
    assert 'aria-current="page"' in nav
    assert css.status_code == 200
    assert "--pamatky-accent" in css.text


def test_health_ok(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PAMATKY_DATA_DIR", str(tmp_path))
    reset_engine()
    from app.main import app

    with TestClient(app) as client:
        response = client.get("/health")
        docs = client.get("/docs")
        openapi = client.get("/openapi.json")
    reset_engine()
    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert docs.status_code == 404
    assert openapi.status_code == 404


def test_catalog_hides_extra_filters_and_keeps_new_place_button(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("PAMATKY_DATA_DIR", str(tmp_path))
    reset_engine()
    from app.main import app

    with TestClient(app) as client:
        page = client.get("/places")
    reset_engine()
    assert page.status_code == 200
    nav = page.text.split("<main", 1)[0]
    assert 'href="/places/new"' not in nav
    assert 'href="/places/new" role="button"' in page.text
    assert "Další filtry" in page.text
    assert "Za návštěvu" in page.text
    assert 'name="worth"' in page.text
    assert "Hledám…" in page.text
    assert 'hx-trigger="load, every 1s [document.getElementById(' in page.text
