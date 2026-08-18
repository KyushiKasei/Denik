from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Visit
from app.services.diary_io import VisitFilters, add_visit, list_visits, soft_delete_visit
from app.services.places import PlaceInput, create_place


def _place_input(**overrides) -> PlaceInput:
    data = PlaceInput(
        name="Bouzov",
        condition="PRESERVED",
        visitability="REGULAR",
        quality_status="VERIFIED",
        municipality="Bouzov",
        country="CZ",
        type_codes=["CASTLE"],
    )
    for key, value in overrides.items():
        setattr(data, key, value)
    return data


def _create_place(client, name: str = "Bouzov") -> str:
    created = client.post(
        "/places",
        data={
            "name": name,
            "condition": "PRESERVED",
            "visitability": "REGULAR",
            "quality_status": "VERIFIED",
            "country": "CZ",
            "municipality": name,
            "type_codes": ["CASTLE"],
        },
        follow_redirects=False,
    )
    assert created.status_code == 303
    return created.headers["location"].split("/")[2].split("?")[0]


def test_visits_page_empty_state(client) -> None:
    page = client.get("/visits")
    assert page.status_code == 200
    assert "Zatím žádná návštěva" in page.text
    assert "Návštěvy" in page.text
    assert "<table>" not in page.text


def test_dashboard_visit_count_links_to_visits(client) -> None:
    home = client.get("/")
    assert home.status_code == 200
    assert 'href="/visits"' in home.text
    assert ">Deník</a>" in home.text
    assert 'href="/diary"' in home.text
    assert 'href="/places?journal=visited"' in home.text


def test_visits_page_lists_and_filters(client) -> None:
    bouzov = _create_place(client, "Bouzov")
    karlstejn = _create_place(client, "Karlštejn")
    client.post(
        f"/places/{bouzov}/visits",
        data={"visited_at": "2026-08-09", "rating": "5", "people": "Petr", "note": "Hrad."},
        follow_redirects=False,
    )
    client.post(
        f"/places/{karlstejn}/visits",
        data={"visited_at": "2026-08-12", "rating": "3", "people": "Jana", "note": "Zámek."},
        follow_redirects=False,
    )

    listing = client.get("/visits")
    assert listing.status_code == 200
    assert "Bouzov" in listing.text
    assert "Karlštejn" in listing.text
    assert f'href="/places/{bouzov}#denik"' in listing.text
    assert "Hrad." in listing.text
    assert "2 návštěv" in listing.text

    by_name = client.get("/visits", params={"q": "Bouzov"})
    assert "Bouzov" in by_name.text
    assert "Karlštejn" not in by_name.text
    assert "1 návštěv" in by_name.text

    by_rating = client.get("/visits", params={"rating": "5"})
    assert "Hrad." in by_rating.text
    assert "Zámek." not in by_rating.text

    by_date = client.get("/visits", params={"date_from": "2026-08-11"})
    assert "Zámek." in by_date.text
    assert "Hrad." not in by_date.text

    empty = client.get("/visits", params={"q": "neexistuje"})
    assert "Žádná návštěva nevyhovuje filtrům" in empty.text


def test_visits_page_hides_soft_deleted_by_default(session: Session) -> None:
    place = create_place(session, _place_input())
    visit = add_visit(session, place, visited_at="2026-08-09", rating=5, people="Petr", note="vidět")
    visible = list_visits(session, VisitFilters())
    assert visible.total == 1
    assert visible.visits[0].public_id == visit.public_id

    soft_delete_visit(session, visit)
    hidden = list_visits(session, VisitFilters())
    assert hidden.total == 0
    shown = list_visits(session, VisitFilters(include_deleted=True))
    assert shown.total == 1
    assert shown.visits[0].deleted_at is not None

    still_there = session.scalar(select(Visit).where(Visit.public_id == visit.public_id))
    assert still_there is not None
    assert still_there.deleted_at is not None


def test_visits_page_shows_soft_deleted_when_asked(client) -> None:
    public_id = _create_place(client)
    client.post(
        f"/places/{public_id}/visits",
        data={"visited_at": "2026-08-09", "rating": "4", "people": "", "note": "Ke smazání."},
        follow_redirects=False,
    )
    detail = client.get(f"/places/{public_id}")
    assert "Ke smazání." in detail.text
    marker = f"/places/{public_id}/visits/"
    start = detail.text.index(marker) + len(marker)
    visit_id = detail.text[start : start + 36]
    deleted = client.post(f"/places/{public_id}/visits/{visit_id}/delete", follow_redirects=False)
    assert deleted.status_code == 303

    listing = client.get("/visits")
    assert "Ke smazání." not in listing.text
    with_deleted = client.get("/visits", params={"deleted": "1"})
    assert "Ke smazání." in with_deleted.text
    assert "smazáno" in with_deleted.text


def test_place_list_shows_journal_column(client) -> None:
    public_id = _create_place(client)
    client.post(
        f"/places/{public_id}/visits",
        data={"visited_at": "2026-08-09", "rating": "4", "people": "", "note": ""},
        follow_redirects=False,
    )
    client.post(
        f"/places/{public_id}/journal",
        data={"want_to_visit": "1", "favorite": "1", "personal_note": ""},
        follow_redirects=False,
    )
    listing = client.get("/places")
    assert listing.status_code == 200
    assert ">Deník</th>" in listing.text
    assert "navštíveno" in listing.text
    assert "chci" in listing.text
    assert "oblíbené" in listing.text


def test_edit_visit_on_place_detail(client) -> None:
    public_id = _create_place(client)
    created = client.post(
        f"/places/{public_id}/visits",
        data={"visited_at": "2026-08-09", "rating": "4", "people": "Petr", "note": "Původní."},
        follow_redirects=False,
    )
    assert created.status_code == 303
    detail = client.get(f"/places/{public_id}")
    marker = f"/places/{public_id}/visits/"
    start = detail.text.index(marker) + len(marker)
    visit_id = detail.text[start : start + 36]
    edit_page = client.get(f"/places/{public_id}", params={"edit": visit_id})
    assert edit_page.status_code == 200
    assert "Upravit návštěvu" in edit_page.text
    assert "Původní." in edit_page.text
    updated = client.post(
        f"/places/{public_id}/visits/{visit_id}",
        data={"visited_at": "2026-08-10", "rating": "5", "people": "Jana", "note": "Upraveno."},
        follow_redirects=False,
    )
    assert updated.status_code == 303
    assert "visit_updated" in updated.headers["location"]
    after = client.get(f"/places/{public_id}")
    assert "Upraveno." in after.text
    assert "Jana" in after.text
    assert "Původní." not in after.text
