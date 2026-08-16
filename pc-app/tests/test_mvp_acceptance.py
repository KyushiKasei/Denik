"""Akceptační scénář MVP (kap. 32) — souborový okruh bez zásahu do SQL."""

from __future__ import annotations

import json
import re

from app.importers.fixture import DEFAULT_FIXTURE
from app.services.catalog_schema import validate_catalog
from app.services.diary_schema import validate_diary

VISIT_A = "0198f93b-618d-762f-a589-ccf375139dd9"
VISIT_B = "0198f93b-618d-762f-a589-ccf375139dda"


def _place_ids(html: str) -> set[str]:
    return set(re.findall(r'href="/places/([0-9a-fA-F-]{36})"', html))


def _diary(place_id: str) -> dict:
    now = "2026-08-09T18:20:00+02:00"
    return {
        "schema_version": 1,
        "exported_at": "2026-08-14T21:00:00+02:00",
        "exported_from": "pwa",
        "place_states": [
            {
                "place_id": place_id,
                "want_to_visit": True,
                "favorite": False,
                "personal_note": None,
                "updated_at": now,
                "deleted_at": None,
            }
        ],
        "visits": [
            {
                "id": VISIT_A,
                "place_id": place_id,
                "visited_at": "2026-08-09",
                "rating": 5,
                "people": ["Jana", "Petr"],
                "note": "Výborná prohlídka.",
                "created_at": now,
                "updated_at": now,
                "deleted_at": None,
            },
            {
                "id": VISIT_B,
                "place_id": place_id,
                "visited_at": "2026-08-11",
                "rating": 4,
                "people": ["Petr"],
                "note": "Druhá návštěva.",
                "created_at": "2026-08-11T12:00:00+02:00",
                "updated_at": "2026-08-11T12:00:00+02:00",
                "deleted_at": None,
            },
        ],
    }


def test_mvp_file_roundtrip_without_sql(client) -> None:
    # 1–2: PC běží, SQLite existuje (TestClient + lifespan).
    home = client.get("/")
    assert home.status_code == 200
    assert "Aktivních míst" in home.text
    assert "Záloha a obnova" in home.text

    # 3: import testovacího katalogu (fixture, ne SQL).
    applied = client.post("/import/apply", data={"fixture": DEFAULT_FIXTURE.name}, follow_redirects=True)
    assert applied.status_code == 200
    listing = client.get("/places")
    assert "Bouzov" in listing.text
    ids_after_first = _place_ids(listing.text)
    assert len(ids_after_first) >= 3

    # 4–5: opakovaný import nevytvoří duplicity, public_id zůstanou.
    client.post("/import/apply", data={"fixture": DEFAULT_FIXTURE.name}, follow_redirects=True)
    catalog_v1 = client.post("/catalog/export").json()
    validate_catalog(catalog_v1)
    assert {item["id"] for item in catalog_v1["places"]} == ids_after_first
    bouzov = next(item for item in catalog_v1["places"] if item["name"] == "Bouzov")
    public_id = bouzov["id"]
    assert public_id in ids_after_first

    # 6: nejasná shoda skončí v review, nové místo Křivoklát se založí.
    client.post("/import/apply", data={"fixture": "small_dataset_update.json"}, follow_redirects=True)
    reviews = client.get("/import/reviews")
    assert reviews.status_code == 200
    assert "Karlstein" in reviews.text or "Q-unclear-karlstein" in reviews.text
    listing_update = client.get("/places")
    assert "Křivoklát" in listing_update.text
    catalog_v2 = client.post("/catalog/export").json()
    assert public_id in {item["id"] for item in catalog_v2["places"]}
    assert public_id == next(item["id"] for item in catalog_v2["places"] if item["name"] == "Bouzov")

    # 7: ruční oprava přežije další import.
    edited = client.post(
        f"/places/{public_id}",
        data={
            "name": "Hrad Bouzov ruční",
            "condition": "PRESERVED",
            "visitability": "REGULAR",
            "quality_status": "VERIFIED",
            "heritage_status": "NKP",
            "country": "CZ",
            "municipality": "Bouzov",
            "district": "Olomouc",
            "region": "Olomoucký kraj",
            "latitude": "49.704",
            "longitude": "16.891",
            "type_codes": ["CASTLE"],
        },
        follow_redirects=True,
    )
    assert edited.status_code == 200
    assert "Hrad Bouzov ruční" in edited.text
    client.post("/import/apply", data={"fixture": DEFAULT_FIXTURE.name}, follow_redirects=True)
    after_import = client.get(f"/places/{public_id}")
    assert "Hrad Bouzov ruční" in after_import.text
    assert public_id in after_import.text

    # 8: export catalog.json (soubor, ne SQL).
    catalog_resp = client.post("/catalog/export")
    assert catalog_resp.status_code == 200
    catalog = catalog_resp.json()
    validate_catalog(catalog)
    assert catalog["places"][0]["id"] == catalog["places"][0]["id"]
    assert all(isinstance(item["id"], str) for item in catalog["places"])
    assert public_id in {item["id"] for item in catalog["places"]}

    # 12–18: diary.json tam i zpět, dvě návštěvy, idempotence.
    payload = json.dumps(_diary(public_id)).encode("utf-8")
    imported = client.post("/diary/import", files={"file": ("diary.json", payload, "application/json")})
    assert imported.status_code == 200
    assert "návštěvy nové: 2" in imported.text
    again = client.post("/diary/import", files={"file": ("diary.json", payload, "application/json")})
    assert again.status_code == 200
    assert "návštěvy nové: 0" in again.text
    detail = client.get(f"/places/{public_id}")
    assert "2026-08-09" in detail.text
    assert "2026-08-11" in detail.text
    assert "Jana, Petr" in detail.text

    exported_diary = client.post("/diary/export")
    assert exported_diary.status_code == 200
    diary = exported_diary.json()
    validate_diary(diary)
    assert {visit["id"] for visit in diary["visits"]} == {VISIT_A, VISIT_B}
    assert all(visit["place_id"] == public_id for visit in diary["visits"])

    # 19–22: aktualizace katalogu (archivace) a nový catalog.json; návštěvy zůstanou.
    archived = client.post(f"/places/{public_id}/archive", follow_redirects=True)
    assert archived.status_code == 200
    catalog_after = client.post("/catalog/export").json()
    validate_catalog(catalog_after)
    assert public_id not in {item["id"] for item in catalog_after["places"]}
    still_there = client.get(f"/places/{public_id}")
    assert still_there.status_code == 200
    assert "2026-08-09" in still_there.text
    assert "2026-08-11" in still_there.text
    assert public_id in still_there.text
