from __future__ import annotations

import json

from sqlalchemy import func, select

from app.db.models import Trip, TripStop
from app.db.session import get_session
from app.services.diary_schema import validate_diary


def _create_place(client, name: str, *, lat: str = "49.704", lon: str = "16.891") -> str:
    created = client.post(
        "/places",
        data={
            "name": name,
            "condition": "PRESERVED",
            "visitability": "REGULAR",
            "quality_status": "VERIFIED",
            "country": "CZ",
            "municipality": name,
            "latitude": lat,
            "longitude": lon,
            "type_codes": ["CASTLE"],
        },
        follow_redirects=False,
    )
    assert created.status_code == 303
    return created.headers["location"].split("/")[2].split("?")[0]


def test_trips_nav_and_empty_list(client) -> None:
    home = client.get("/")
    assert 'href="/trips"' in home.text
    page = client.get("/trips")
    assert page.status_code == 200
    assert "Zatím žádný výlet" in page.text
    assert "Nový výlet" in page.text


def test_trips_crud_add_reorder_and_air_km(client) -> None:
    bouzov = _create_place(client, "Bouzov", lat="49.704", lon="16.891")
    karlstejn = _create_place(client, "Karlštejn", lat="49.939", lon="14.188")

    created = client.post(
        "/trips",
        data={"name": "Olomoucko", "planned_on": "2026-08-20"},
        follow_redirects=False,
    )
    assert created.status_code == 303
    trip_id = created.headers["location"].split("/")[2].split("?")[0]

    listing = client.get("/trips")
    assert "Olomoucko" in listing.text
    assert "2026-08-20" in listing.text

    added = client.post(
        f"/trips/{trip_id}/stops",
        data={"place_public_id": bouzov},
        follow_redirects=False,
    )
    assert added.status_code == 303
    client.post(f"/trips/{trip_id}/stops", data={"place_public_id": karlstejn}, follow_redirects=False)

    detail = client.get(f"/trips/{trip_id}")
    assert detail.status_code == 200
    assert "Bouzov" in detail.text
    assert "Karlštejn" in detail.text
    assert "km vzdušnou čarou" in detail.text
    assert "Hrad" in detail.text
    assert "Běžně přístupné" in detail.text
    assert 'class="trip-row"' in detail.text

    client.post(f"/trips/{trip_id}/stops/{bouzov}/down", follow_redirects=False)
    after_move = client.get(f"/trips/{trip_id}").text
    assert after_move.find("Karlštejn") < after_move.find("Bouzov")

    client.post(f"/trips/{trip_id}/stops/{karlstejn}/delete", follow_redirects=False)
    after_remove = client.get(f"/trips/{trip_id}")
    assert "Karlštejn" not in after_remove.text
    assert "Bouzov" in after_remove.text

    saved = client.post(
        f"/trips/{trip_id}",
        data={"name": "Haná", "planned_on": "2026-08-21", "notes": "snídaně v Olomouci"},
        follow_redirects=False,
    )
    assert saved.status_code == 303
    renamed = client.get(f"/trips/{trip_id}")
    assert "Haná" in renamed.text
    assert "snídaně v Olomouci" in renamed.text

    deleted = client.post(f"/trips/{trip_id}/delete", follow_redirects=False)
    assert deleted.status_code == 303
    empty = client.get("/trips")
    assert "Haná" not in empty.text

    db = get_session()
    try:
        trip = db.scalar(select(Trip).where(Trip.public_id == trip_id))
        assert trip is not None
        assert trip.deleted_at is not None
        assert db.scalar(select(func.count()).select_from(TripStop)) == 1
    finally:
        db.close()


def test_diary_import_export_trips_roundtrip(client) -> None:
    public_id = _create_place(client, "Bouzov")
    trip_id = "0198f93b-618d-762f-a589-ccf375139dd8"
    diary = {
        "schema_version": 2,
        "exported_at": "2026-08-16T10:00:00+02:00",
        "exported_from": "pwa",
        "place_states": [],
        "visits": [],
        "trips": [
            {
                "id": trip_id,
                "name": "Olomoucko",
                "planned_on": "2026-08-20",
                "origin": None,
                "notes": None,
                "stops": [{"place_id": public_id, "sort_order": 0, "note": None}],
                "created_at": "2026-08-16T10:00:00+02:00",
                "updated_at": "2026-08-16T10:00:00+02:00",
                "deleted_at": None,
            }
        ],
    }
    payload = json.dumps(diary).encode("utf-8")
    imported = client.post("/diary/import", files={"file": ("diary.json", payload, "application/json")})
    assert imported.status_code == 200
    assert "výlety nové: 1" in imported.text

    again = client.post("/diary/import", files={"file": ("diary.json", payload, "application/json")})
    assert "výlety nové: 0" in again.text

    listing = client.get("/trips")
    assert "Olomoucko" in listing.text
    detail = client.get(f"/trips/{trip_id}")
    assert "Bouzov" in detail.text

    exported = client.post("/diary/export")
    data = exported.json()
    validate_diary(data)
    assert data["schema_version"] == 2
    assert data["trips"][0]["id"] == trip_id
    assert data["trips"][0]["stops"][0]["place_id"] == public_id


def test_trip_search_shows_type_and_compact_add(client) -> None:
    trip_id = client.post(
        "/trips",
        data={"name": "Výlet", "planned_on": "2099-06-01"},
        follow_redirects=False,
    ).headers["location"].split("/")[2].split("?")[0]
    _create_place(client, "Kovozoo Staré Město")

    page = client.get(f"/trips/{trip_id}?q=zoo")
    assert page.status_code == 200
    assert "Kovozoo Staré Město" in page.text
    assert "Hrad" in page.text
    assert "Běžně přístupné" in page.text
    html = page.text
    name_at = html.find("Kovozoo Staré Město")
    add_at = html.find(">Přidat<", name_at)
    assert 0 <= name_at < add_at
    assert 'class="trip-row"' in html


def test_place_detail_adds_only_to_upcoming_trip(client) -> None:
    place_id = _create_place(client, "Bouzov")
    past = client.post(
        "/trips",
        data={"name": "Minulý", "planned_on": "2000-01-01"},
        follow_redirects=False,
    ).headers["location"].split("/")[2].split("?")[0]
    future = client.post(
        "/trips",
        data={"name": "Budoucí", "planned_on": "2099-06-01"},
        follow_redirects=False,
    ).headers["location"].split("/")[2].split("?")[0]

    detail = client.get(f"/places/{place_id}")
    assert "Přidat na výlet" in detail.text
    assert "Budoucí" in detail.text
    assert "Minulý" not in detail.text
    assert f'value="{future}"' in detail.text
    assert f'value="{past}"' not in detail.text

    added = client.post(
        f"/places/{place_id}/trips",
        data={"trip_public_id": future},
        follow_redirects=False,
    )
    assert added.status_code == 303
    assert added.headers["location"] == f"/places/{place_id}?notice=trip_stop_added"
    trip_page = client.get(f"/trips/{future}")
    assert "Bouzov" in trip_page.text

    ignored = client.post(
        f"/places/{place_id}/trips",
        data={"trip_public_id": past},
        follow_redirects=False,
    )
    assert ignored.status_code == 303
    past_page = client.get(f"/trips/{past}")
    assert "Bouzov" not in past_page.text


def test_default_trip_name_uses_date(client) -> None:
    page = client.get("/trips")
    assert page.status_code == 200
    assert "Výlet " in page.text
    from app.services.trips import default_trip_name

    assert default_trip_name("2026-08-18") == "Výlet 18. 8. 2026"
