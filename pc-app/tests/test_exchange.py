from __future__ import annotations

import json
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

from fastapi.testclient import TestClient

from app.config import REPO_ROOT
from app.services.exchange import (
    ExchangeError,
    find_incoming_diary,
    save_exchange_folder,
)
from app.services.lan_sync import current_pin, reset_lan_state, start_lan_session
from app.web.lan_app import lan_app

SAMPLE_DIARY = REPO_ROOT / "fixtures" / "diary.sample.json"


def _phone_dir(tmp_path: Path) -> Path:
    folder = tmp_path.resolve().parent / f"{tmp_path.name}-phone"
    folder.mkdir(exist_ok=True)
    return folder


def test_admin_nav_has_subtabs(client):
    home = client.get("/")
    assert home.status_code == 200
    home_nav = home.text.split("<main", 1)[0]
    assert "Administrace" in home_nav
    assert 'href="/exchange"' in home_nav
    assert "admin-subnav" not in home_nav
    assert "Import památek" not in home_nav
    assert home_nav.find("/nearby") < home_nav.find("/exchange")

    exchange = client.get("/exchange")
    assert exchange.status_code == 200
    assert "admin-subnav" in exchange.text
    assert "Výměna dat" in exchange.text
    assert "Import památek" in exchange.text
    assert "Exportovat catalog.json" in exchange.text

    imported = client.get("/import")
    assert imported.status_code == 200
    assert "Import centrum" in imported.text
    assert "Import památek" in imported.text
    assert "admin-subnav" in imported.text

    backup = client.get("/backup")
    assert backup.status_code == 200
    assert "admin-subnav" in backup.text
    assert "Vytvořit zálohu teď" in backup.text


def test_dashboard_shows_exchange_panel(client):
    home = client.get("/")
    assert home.status_code == 200
    assert "Složka pro telefon" not in home.text
    page = client.get("/exchange")
    assert page.status_code == 200
    assert "Složka pro telefon" in page.text
    assert "QR otevře Safari, nespáruje PWA" in page.text


def test_save_exchange_folder_rejects_data_dir(client, tmp_path):
    response = client.post("/exchange/folder", data={"folder": str(tmp_path)}, follow_redirects=True)
    assert response.status_code == 200
    assert "živé databáze" in response.text
    assert not (tmp_path / "exchange.json").is_file()


def test_save_and_merge_diary_from_exchange_folder(client, tmp_path):
    phone = _phone_dir(tmp_path)
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

    sample = json.loads(SAMPLE_DIARY.read_text(encoding="utf-8"))
    sample["visits"][0]["place_id"] = public_id
    sample["place_states"][0]["place_id"] = public_id
    (phone / "diary.zip").write_bytes(_zip_diary(sample))
    (phone / "diary-z-pc.zip").write_bytes(b"old")

    saved = client.post("/exchange/folder", data={"folder": str(phone)}, follow_redirects=True)
    assert saved.status_code == 200
    assert "Složka pro telefon je uložená." in saved.text
    assert "čeká diary.zip" in saved.text

    merged = client.post("/exchange/import-diary", follow_redirects=True)
    assert merged.status_code == 200
    assert "návštěvy nové: 1" in merged.text
    assert "diary-z-pc.zip" in merged.text

    outgoing = phone / "diary-z-pc.zip"
    assert outgoing.is_file()
    with ZipFile(BytesIO(outgoing.read_bytes())) as archive:
        exported = json.loads(archive.read("diary.json").decode("utf-8"))
    assert exported["visits"][0]["place_id"] == public_id
    assert exported["visits"][0]["id"] == sample["visits"][0]["id"]

    catalog = client.post("/exchange/catalog", follow_redirects=True)
    assert catalog.status_code == 200
    assert "catalog.json je ve složce pro telefon." in catalog.text
    data = json.loads((phone / "catalog.json").read_text(encoding="utf-8"))
    assert any(place["id"] == public_id for place in data["places"])


def test_merge_without_incoming_diary_is_400(client, tmp_path):
    phone = _phone_dir(tmp_path)
    (phone / "diary-z-pc.zip").write_bytes(b"not-incoming")
    saved = client.post("/exchange/folder", data={"folder": str(phone)}, follow_redirects=True)
    assert saved.status_code == 200
    missing = client.post("/exchange/import-diary")
    assert missing.status_code == 400
    assert "diary.zip ani diary.json" in missing.text


def test_find_incoming_diary_ignores_outgoing_and_picks_newest(tmp_path, monkeypatch):
    monkeypatch.setenv("PAMATKY_DATA_DIR", str(tmp_path / "data"))
    phone = tmp_path / "phone"
    phone.mkdir()
    (phone / "diary-z-pc.zip").write_bytes(b"pc")
    older = phone / "diary.json"
    newer = phone / "diary.zip"
    older.write_text("{}", encoding="utf-8")
    newer.write_bytes(b"PK")
    assert find_incoming_diary(phone) == newer


def test_save_exchange_folder_strips_quotes(tmp_path, monkeypatch):
    monkeypatch.setenv("PAMATKY_DATA_DIR", str(tmp_path / "data"))
    phone = tmp_path / "inbox"
    saved = save_exchange_folder(f'"{phone}"')
    assert saved == phone.resolve()
    assert saved.is_dir()


def test_save_exchange_folder_empty_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("PAMATKY_DATA_DIR", str(tmp_path))
    try:
        save_exchange_folder("  ")
        raise AssertionError("expected ExchangeError")
    except ExchangeError as exc:
        assert "Zadejte cestu" in str(exc)


def test_lan_page_says_safari_is_not_pwa():
    start_lan_session(listen=False)
    lan = TestClient(lan_app)
    try:
        home = lan.get("/lan")
        assert home.status_code == 200
        assert "Toto není deník z telefonu" in home.text
        assert "nespároval s PWA" in home.text
        pin = current_pin()
        unlocked = lan.post("/lan/unlock", data={"pin": pin}, follow_redirects=True)
        assert unlocked.status_code == 200
        assert "PWA na ploše" in unlocked.text
        assert "2. Nahrát diary" in unlocked.text
        assert "Stáhnout sloučený diary.zip" in unlocked.text
    finally:
        reset_lan_state()


def _zip_diary(sample: dict) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("diary.json", json.dumps(sample, ensure_ascii=False, indent=2) + "\n")
    return buffer.getvalue()
