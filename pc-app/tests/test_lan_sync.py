from __future__ import annotations

import json
from io import BytesIO
from zipfile import ZipFile

from fastapi.testclient import TestClient

from app.services.lan_sync import current_pin, expire_lan_session_for_tests, reset_lan_state, start_lan_session
from app.web.lan_app import lan_app

SAMPLE = {
    "schema_version": 2,
    "exported_at": "2026-08-14T21:00:00+02:00",
    "exported_from": "pwa",
    "place_states": [],
    "visits": [
        {
            "id": "0198f93b-618d-762f-a589-ccf375139dd9",
            "place_id": "0198f23a-5e5e-7b31-a8be-8c99507a2138",
            "visited_at": "2026-08-09",
            "rating": 5,
            "people": ["Jana", "Petr"],
            "note": "Výborná prohlídka.",
            "created_at": "2026-08-09T18:20:00+02:00",
            "updated_at": "2026-08-09T18:20:00+02:00",
            "deleted_at": None,
        }
    ],
    "trips": [],
}


def _lan_client() -> TestClient:
    start_lan_session(listen=False)
    return TestClient(lan_app)


def _unlock(client: TestClient, pin: str | None = None) -> None:
    response = client.post("/lan/unlock", data={"pin": pin or current_pin()}, follow_redirects=True)
    assert response.status_code == 200
    assert "Nahrát diary" in response.text


def test_lan_without_session_is_403():
    reset_lan_state()
    response = TestClient(lan_app).get("/lan")
    assert response.status_code == 403
    assert "není zapnutá" in response.text


def test_lan_page_disables_double_submit():
    lan = _lan_client()
    page = lan.get("/lan")
    assert page.status_code == 200
    assert "dataset.submitting" in page.text


def test_lan_without_pin_cannot_download(client):
    lan = _lan_client()
    denied = lan.get("/lan/diary.zip")
    assert denied.status_code == 403
    catalog = lan.get("/lan/catalog.json")
    assert catalog.status_code == 403
    uploaded = lan.post("/lan/import", files={"file": ("diary.json", b"{}", "application/json")})
    assert uploaded.status_code == 403


def test_wrong_pin_is_403(client):
    lan = _lan_client()
    response = lan.post("/lan/unlock", data={"pin": "000000"})
    assert response.status_code == 403
    assert "PIN nesedí" in response.text


def test_expired_session_is_403(client):
    lan = _lan_client()
    expire_lan_session_for_tests()
    response = lan.get("/lan")
    assert response.status_code == 403


def test_unlock_then_import_merge_and_downloads(client):
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
    diary = json.loads(json.dumps(SAMPLE))
    diary["visits"][0]["place_id"] = public_id
    diary["place_states"] = [
        {
            "place_id": public_id,
            "want_to_visit": True,
            "favorite": False,
            "personal_note": None,
            "updated_at": "2026-08-09T18:20:00+02:00",
            "deleted_at": None,
        }
    ]

    lan = _lan_client()
    home = lan.get("/lan")
    assert home.status_code == 200
    assert "PIN z obrazovky PC" in home.text
    _unlock(lan)

    payload = json.dumps(diary).encode("utf-8")
    imported = lan.post("/lan/import", files={"file": ("diary.json", payload, "application/json")})
    assert imported.status_code == 200
    assert "návštěvy nové: 1" in imported.text

    again = lan.post("/lan/import", files={"file": ("diary.json", payload, "application/json")})
    assert again.status_code == 200
    assert "návštěvy nové: 0" in again.text

    zipped = lan.get("/lan/diary.zip")
    assert zipped.status_code == 200
    assert "diary.zip" in zipped.headers.get("content-disposition", "")
    with ZipFile(BytesIO(zipped.content)) as archive:
        exported = json.loads(archive.read("diary.json").decode("utf-8"))
    assert exported["visits"][0]["id"] == SAMPLE["visits"][0]["id"]
    assert exported["visits"][0]["place_id"] == public_id

    catalog = lan.get("/lan/catalog.json")
    assert catalog.status_code == 200
    data = catalog.json()
    assert data["schema_version"] == 1
    assert any(place["id"] == public_id for place in data["places"])


def test_unlock_then_expire_blocks_download(client):
    lan = _lan_client()
    _unlock(lan)
    expire_lan_session_for_tests()
    response = lan.get("/lan/diary.zip")
    assert response.status_code == 403


def test_dashboard_enable_shows_pin(client):
    home = client.get("/")
    assert home.status_code == 200
    assert "Domácí Wi-Fi" not in home.text
    page = client.get("/exchange")
    assert page.status_code == 200
    assert "Domácí Wi-Fi" in page.text
    enabled = client.post("/lan/enable", follow_redirects=True)
    assert enabled.status_code == 200
    pin = current_pin()
    assert pin is not None
    assert pin in enabled.text
    disabled = client.post("/lan/disable", follow_redirects=True)
    assert disabled.status_code == 200
    assert current_pin() is None
