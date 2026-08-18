from __future__ import annotations

from app.services.diary_io import today_iso_date
from app.services.visit_photos import save_visit_photo


def _create_place(client, name: str = "Bouzov", *, region: str = "Olomoucký kraj", lat: str = "49.704", lon: str = "16.891") -> str:
    created = client.post(
        "/places",
        data={
            "name": name,
            "condition": "PRESERVED",
            "visitability": "REGULAR",
            "quality_status": "VERIFIED",
            "country": "CZ",
            "municipality": name,
            "region": region,
            "latitude": lat,
            "longitude": lon,
            "type_codes": ["CASTLE"],
        },
        follow_redirects=False,
    )
    assert created.status_code == 303
    return created.headers["location"].split("/")[2].split("?")[0]


def _visit_id(client, public_id: str) -> str:
    detail = client.get(f"/places/{public_id}")
    marker = f"/places/{public_id}/visits/"
    start = detail.text.index(marker) + len(marker)
    return detail.text[start : start + 36]


def test_diary_passport_and_yearbook_pages(client) -> None:
    public_id = _create_place(client)
    client.post(
        f"/places/{public_id}/visits",
        data={"visited_at": "2026-08-09", "rating": "5", "people": "Petr", "note": "Otisk."},
        follow_redirects=False,
    )
    home = client.get("/")
    assert home.status_code == 200
    assert 'href="/diary"' in home.text
    assert "Poslední otisky" in home.text
    assert "Bouzov" in home.text
    assert "stamp-mark" in home.text

    pas = client.get("/diary")
    assert pas.status_code == 200
    assert "Olomoucký kraj" in pas.text
    assert "Bouzov" in pas.text
    assert "První návštěva" in pas.text
    assert "stamp-mark" in pas.text
    assert 'href="/yearbook"' in pas.text

    olk = client.get("/diary", params={"region": "OLK"})
    assert olk.status_code == 200
    assert "Bouzov" in olk.text

    yearbook = client.get("/yearbook")
    assert yearbook.status_code == 200
    assert "Můj rok" in yearbook.text
    assert "Bouzov" in yearbook.text
    assert "Petr" in yearbook.text
    assert "Atlas tohoto roku" in yearbook.text
    assert "until=" in yearbook.text

    visits = client.get("/visits")
    assert visits.status_code == 200
    assert "stamp-mark" in visits.text
    assert "Pas s razítky" in visits.text


def test_atlas_page_shows_visited_marker(client) -> None:
    public_id = _create_place(client)
    client.post(
        f"/places/{public_id}/visits",
        data={"visited_at": "2026-08-09", "rating": "", "people": "", "note": ""},
        follow_redirects=False,
    )
    atlas = client.get("/nearby", params={"view": "atlas"})
    assert atlas.status_code == 200
    assert "Atlas" in atlas.text
    assert "Bouzov" in atlas.text
    assert "nearby-map-data" in atlas.text
    assert "atlas" in atlas.text
    assert "timeline" in atlas.text
    assert 'id="atlas-time"' in atlas.text
    until_page = client.get("/nearby", params={"view": "atlas", "until": "2026-08-09"})
    assert until_page.status_code == 200
    assert "2026-08-09" in until_page.text
    assert "timeline" in until_page.text


def test_dashboard_trip_today_and_visit_photo(client) -> None:
    public_id = _create_place(client)
    created = client.post(
        f"/places/{public_id}/visits",
        data={"visited_at": today_iso_date(), "rating": "", "people": "", "note": ""},
        follow_redirects=False,
    )
    assert created.status_code == 303
    visit_id = _visit_id(client, public_id)
    save_visit_photo(visit_id, "cafe.jpg", b"jpeg-bytes")
    trip = client.post(
        "/trips",
        data={"name": "Dnešní okruh", "planned_on": today_iso_date()},
        follow_redirects=False,
    )
    assert trip.status_code == 303
    trip_id = trip.headers["location"].split("/")[2].split("?")[0]
    client.post(f"/trips/{trip_id}/stops", data={"place_public_id": public_id}, follow_redirects=False)

    home = client.get("/")
    assert home.status_code == 200
    assert "Dnešní výlet" in home.text
    assert "Dnešní okruh" in home.text
    listing = client.get("/visits")
    assert f"/visit-photos/{visit_id}/cafe.jpg" in listing.text
    photo = client.get(f"/visit-photos/{visit_id}/cafe.jpg")
    assert photo.status_code == 200
    assert photo.content == b"jpeg-bytes"
    assert client.get("/visit-photos/../cafe.jpg").status_code == 404
    assert client.get(f"/visit-photos/{visit_id}/../cafe.jpg").status_code == 404
    detail = client.get(f"/places/{public_id}")
    assert "stamp-mark" in detail.text
