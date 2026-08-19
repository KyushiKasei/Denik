from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.datastructures import FormData

from app.db.models import Place, PlacePhoto
from app.db.session import get_session
from app.services.overrides import upsert_override
from app.services.places import PlaceFilters, PlaceInput, create_place, list_places, mark_ruins_free_access


def _payload(**overrides) -> dict[str, str | list[str]]:
    data: dict[str, str | list[str]] = {
        "name": "Bouzov",
        "condition": "PRESERVED",
        "visitability": "REGULAR",
        "quality_status": "VERIFIED",
        "country": "CZ",
        "municipality": "Bouzov",
        "district": "Olomouc",
        "region": "Olomoucký kraj",
        "latitude": "49.704",
        "longitude": "16.891",
        "official_website": "https://www.hrad-bouzov.cz/",
        "type_codes": ["CASTLE"],
    }
    data.update(overrides)
    return data


def test_empty_catalog_list_message(client) -> None:
    listing = client.get("/places")
    assert listing.status_code == 200
    assert "Katalog je prázdný" in listing.text
    assert "Žádné místo nevyhovuje filtrům." not in listing.text
    assert "Přístupné veřejnosti (0)" in listing.text
    assert "Neznámé (0)" in listing.text


def _public_id_from_db(name: str = "Bouzov") -> str:
    session = get_session()
    try:
        place = session.scalar(select(Place).where(Place.name == name))
        assert place is not None
        return place.public_id
    finally:
        session.close()


def test_create_place(client) -> None:
    response = client.post("/places", data=_payload(), follow_redirects=False)
    assert response.status_code == 303
    public_id = _public_id_from_db()
    assert response.headers["location"] == f"/places/{public_id}?notice=created"
    detail = client.get(f"/places/{public_id}")
    assert detail.status_code == 200
    assert "Bouzov" in detail.text
    assert "Hrad" in detail.text
    assert public_id in detail.text
    listing = client.get("/places")
    assert "place-list-thumb is-empty" in listing.text


def test_place_detail_does_not_link_javascript_urls(client) -> None:
    client.post("/places", data=_payload())
    public_id = _public_id_from_db()
    session = get_session()
    try:
        place = session.scalar(select(Place).where(Place.public_id == public_id))
        assert place is not None
        place.wikipedia_url = "javascript:alert(1)"
        place.official_website = "javascript:alert(2)"
        place.opening_hours_url = "javascript:alert(3)"
        place.ticket_url = "javascript:alert(4)"
        session.commit()
    finally:
        session.close()
    detail = client.get(f"/places/{public_id}")
    assert detail.status_code == 200
    assert 'href="javascript:' not in detail.text
    assert "javascript:alert(1)" in detail.text


def test_place_pages_show_catalog_photo(client) -> None:
    client.post("/places", data=_payload())
    public_id = _public_id_from_db()
    thumb = "https://commons.wikimedia.org/wiki/Special:FilePath/Hrad_Bouzov.jpg?width=640"
    session = get_session()
    try:
        place = session.scalar(select(Place).where(Place.public_id == public_id))
        assert place is not None
        session.add(
            PlacePhoto(
                place_id=place.id,
                source="wikimedia_commons",
                thumbnail_url=thumb,
                original_url="https://commons.wikimedia.org/wiki/File:Hrad_Bouzov.jpg",
                attribution="Jan Novák",
                license="CC BY-SA 4.0",
                license_url="https://creativecommons.org/licenses/by-sa/4.0/",
                is_primary=1,
            )
        )
        session.commit()
    finally:
        session.close()

    detail = client.get(f"/places/{public_id}")
    assert detail.status_code == 200
    assert thumb in detail.text
    assert "Jan Novák" in detail.text
    assert "CC BY-SA 4.0" in detail.text
    listing = client.get("/places?q=Bouzov")
    assert listing.status_code == 200
    assert thumb in listing.text
    assert "place-list-thumb" in listing.text


def test_archived_place_hidden_from_default_list_but_kept_in_db(client) -> None:
    client.post("/places", data=_payload())
    public_id = _public_id_from_db()
    archive = client.post(f"/places/{public_id}/archive", follow_redirects=False)
    assert archive.status_code == 303

    listing = client.get("/places")
    assert listing.status_code == 200
    assert f'href="/places/{public_id}"' not in listing.text
    assert "Žádné místo nevyhovuje filtrům." in listing.text

    archived_listing = client.get("/places?archived=archived")
    assert "Bouzov" in archived_listing.text

    session = get_session()
    try:
        place = session.scalar(select(Place).where(Place.public_id == public_id))
        assert place is not None
        assert place.archived_at is not None
        assert place.public_id == public_id
        assert place.name == "Bouzov"
    finally:
        session.close()


def test_place_can_have_two_types(client) -> None:
    response = client.post(
        "/places",
        data=_payload(name="Bečov nad Teplou", type_codes=["CASTLE", "CHATEAU"]),
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Hrad a zámek" in response.text
    session = get_session()
    try:
        place = session.scalar(select(Place).where(Place.name == "Bečov nad Teplou"))
        assert place is not None
        assert {item.code for item in place.types} == {"CASTLE", "CHATEAU"}
    finally:
        session.close()


def test_coordinate_validation_rejects_out_of_range(client) -> None:
    response = client.post(
        "/places",
        data=_payload(latitude="99", longitude="16.8"),
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "Zeměpisná šířka musí být mezi" in response.text
    session = get_session()
    try:
        assert session.scalar(select(Place)) is None
    finally:
        session.close()


def test_coordinate_validation_requires_both_or_neither(client) -> None:
    response = client.post(
        "/places",
        data=_payload(latitude="49.7", longitude=""),
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "obě souřadnice" in response.text


def test_coordinate_validation_rejects_non_numeric(client) -> None:
    response = client.post(
        "/places",
        data=_payload(latitude="sever", longitude="16.8"),
        follow_redirects=False,
    )
    assert response.status_code == 400
    assert "Neplatné číslo" in response.text


def test_phase2_acceptance_create_edit_archive_same_public_id(client) -> None:
    created = client.post("/places", data=_payload(type_codes=[]), follow_redirects=True)
    assert created.status_code == 200
    public_id = _public_id_from_db()
    assert public_id in created.text

    edited = client.post(
        f"/places/{public_id}",
        data=_payload(name="Hrad Bouzov", type_codes=["CASTLE"]),
        follow_redirects=True,
    )
    assert edited.status_code == 200
    assert "Hrad Bouzov" in edited.text
    assert public_id in edited.text
    assert "Hrad" in edited.text

    client.post(f"/places/{public_id}/archive")
    active = client.get("/places")
    assert f'href="/places/{public_id}"' not in active.text

    archived = client.get("/places?archived=archived")
    assert "Hrad Bouzov" in archived.text

    session = get_session()
    try:
        place = session.scalar(select(Place).where(Place.public_id == public_id))
        assert place is not None
        assert place.name == "Hrad Bouzov"
        assert place.archived_at is not None
        assert {item.code for item in place.types} == {"CASTLE"}
    finally:
        session.close()


def test_update_ignores_posted_public_id(client) -> None:
    client.post("/places", data=_payload())
    public_id = _public_id_from_db()
    payload = _payload(name="Bouzov")
    payload["public_id"] = "00000000-0000-7000-0000-000000000000"
    client.post(f"/places/{public_id}", data=payload)
    session = get_session()
    try:
        place = session.scalar(select(Place).where(Place.id == 1))
        assert place is not None
        assert place.public_id == public_id
    finally:
        session.close()


def test_list_filters_missing_gps_and_type(session: Session) -> None:
    with_gps = PlaceInput.from_form(
        FormData(
            [
                ("name", "S GPS"),
                ("type_codes", "CASTLE"),
                ("condition", "UNKNOWN"),
                ("visitability", "UNKNOWN"),
                ("quality_status", "VERIFIED"),
                ("latitude", "50.0"),
                ("longitude", "14.0"),
            ]
        )
    )
    without = PlaceInput.from_form(
        FormData(
            [
                ("name", "Bez GPS"),
                ("condition", "UNKNOWN"),
                ("visitability", "UNKNOWN"),
                ("quality_status", "NEEDS_REVIEW"),
            ]
        )
    )
    create_place(session, with_gps)
    create_place(session, without)

    missing_gps = list_places(session, PlaceFilters(missing_gps=True, worth=False))
    assert [place.name for place in missing_gps.places] == ["Bez GPS"]

    missing_type = list_places(session, PlaceFilters(missing_type=True, worth=False))
    assert [place.name for place in missing_type.places] == ["Bez GPS"]

    castles = list_places(session, PlaceFilters(type_code="CASTLE", worth=False))
    assert [place.name for place in castles.places] == ["S GPS"]


def test_visitability_public_group_filter(session: Session) -> None:
    create_place(
        session,
        PlaceInput.from_form(
            FormData(
                [
                    ("name", "Otevřený"),
                    ("condition", "UNKNOWN"),
                    ("visitability", "SEASONAL"),
                    ("quality_status", "VERIFIED"),
                ]
            )
        ),
    )
    create_place(
        session,
        PlaceInput.from_form(
            FormData(
                [
                    ("name", "Soukromý"),
                    ("condition", "UNKNOWN"),
                    ("visitability", "PRIVATE"),
                    ("quality_status", "VERIFIED"),
                ]
            )
        ),
    )
    create_place(
        session,
        PlaceInput.from_form(
            FormData(
                [
                    ("name", "Neznámý"),
                    ("condition", "UNKNOWN"),
                    ("visitability", "UNKNOWN"),
                    ("quality_status", "VERIFIED"),
                ]
            )
        ),
    )
    public = list_places(session, PlaceFilters(visitability="PUBLIC", worth=False))
    assert [place.name for place in public.places] == ["Otevřený"]
    closed = list_places(session, PlaceFilters(visitability="NOT_PUBLIC", worth=False))
    assert [place.name for place in closed.places] == ["Soukromý"]


def test_visitability_facet_counts_respect_other_filters(session: Session) -> None:
    from app.services.places import filter_facet_counts

    create_place(
        session,
        PlaceInput.from_form(
            FormData(
                [
                    ("name", "Otevřený hrad"),
                    ("type_codes", "CASTLE"),
                    ("condition", "UNKNOWN"),
                    ("visitability", "REGULAR"),
                    ("quality_status", "VERIFIED"),
                    ("region", "Olomoucký kraj"),
                ]
            )
        ),
    )
    create_place(
        session,
        PlaceInput.from_form(
            FormData(
                [
                    ("name", "Otevřený zámek"),
                    ("type_codes", "CHATEAU"),
                    ("condition", "UNKNOWN"),
                    ("visitability", "SEASONAL"),
                    ("quality_status", "VERIFIED"),
                    ("region", "Jihočeský kraj"),
                ]
            )
        ),
    )
    create_place(
        session,
        PlaceInput.from_form(
            FormData(
                [
                    ("name", "Neznámý zámek"),
                    ("type_codes", "CHATEAU"),
                    ("condition", "UNKNOWN"),
                    ("visitability", "UNKNOWN"),
                    ("quality_status", "VERIFIED"),
                    ("region", "Jihočeský kraj"),
                ]
            )
        ),
    )
    all_counts = filter_facet_counts(session, PlaceFilters(worth=False))
    assert all_counts.visitability["PUBLIC"] == 2
    assert all_counts.visitability["UNKNOWN"] == 1
    assert all_counts.visitability[""] == 3
    south = filter_facet_counts(session, PlaceFilters(region="Jihočeský kraj", worth=False))
    assert south.visitability["PUBLIC"] == 1
    assert south.visitability["UNKNOWN"] == 1
    assert south.types["CHATEAU"] == 2
    assert south.types.get("CASTLE", 0) == 0


def test_dashboard_type_counts_count_mn(client) -> None:
    client.post("/places", data=_payload(name="Bečov", type_codes=["CASTLE", "CHATEAU"]))
    client.post("/places", data=_payload(name="Bouzov", type_codes=["CASTLE"]))
    home = client.get("/")
    assert home.status_code == 200
    assert "Aktivních míst" in home.text
    assert "<strong>2</strong>" in home.text
    assert "Zříceniny (typ nebo stav)" in home.text


def test_search_matches_public_id_and_source_external_id(session: Session) -> None:
    from app.db.models import PlaceSource

    place = create_place(
        session,
        PlaceInput.from_form(
            FormData(
                [
                    ("name", "Bouzov"),
                    ("condition", "PRESERVED"),
                    ("visitability", "REGULAR"),
                    ("quality_status", "VERIFIED"),
                    ("type_codes", "CASTLE"),
                ]
            )
        ),
    )
    other = create_place(
        session,
        PlaceInput.from_form(
            FormData(
                [
                    ("name", "Karlštejn"),
                    ("condition", "PRESERVED"),
                    ("visitability", "REGULAR"),
                    ("quality_status", "VERIFIED"),
                    ("type_codes", "CASTLE"),
                ]
            )
        ),
    )
    session.add(PlaceSource(place_id=place.id, source_type="wikidata", external_id="Q122922"))
    session.commit()

    by_id = list_places(session, PlaceFilters(q=place.public_id))
    assert [row.name for row in by_id.places] == ["Bouzov"]
    by_qid = list_places(session, PlaceFilters(q="Q122922"))
    assert [row.name for row in by_qid.places] == ["Bouzov"]
    by_name = list_places(session, PlaceFilters(q="Karlštejn"))
    assert [row.name for row in by_name.places] == ["Karlštejn"]
    assert other.name == "Karlštejn"


def test_clear_filters_link_shown_when_active(client) -> None:
    client.post("/places", data=_payload())
    filtered = client.get("/places?q=Bouzov")
    assert filtered.status_code == 200
    assert "Zrušit filtry" in filtered.text
    assert 'href="/places"' in filtered.text
    listing = client.get("/places")
    assert "Zrušit filtry" not in listing.text
    all_places = client.get("/places?worth=all")
    assert "Zrušit filtry" in all_places.text


def test_worth_filter_hides_extinct_private_and_stubs(session: Session) -> None:
    from app.services.places import filter_facet_counts

    ruin = create_place(
        session,
        PlaceInput.from_form(
            FormData(
                [
                    ("name", "Zřícenina"),
                    ("condition", "RUIN"),
                    ("visitability", "FREE_ACCESS"),
                    ("quality_status", "VERIFIED"),
                    ("type_codes", "RUIN"),
                ]
            )
        ),
    )
    create_place(
        session,
        PlaceInput.from_form(
            FormData(
                [
                    ("name", "Zaniklý"),
                    ("condition", "EXTINCT"),
                    ("visitability", "EXTINCT"),
                    ("quality_status", "VERIFIED"),
                    ("type_codes", "CASTLE"),
                ]
            )
        ),
    )
    create_place(
        session,
        PlaceInput.from_form(
            FormData(
                [
                    ("name", "Soukromý"),
                    ("condition", "PRESERVED"),
                    ("visitability", "PRIVATE"),
                    ("quality_status", "VERIFIED"),
                    ("type_codes", "CHATEAU"),
                ]
            )
        ),
    )
    stub = create_place(
        session,
        PlaceInput.from_form(
            FormData(
                [
                    ("name", "Neznámý"),
                    ("condition", "UNKNOWN"),
                    ("visitability", "UNKNOWN"),
                    ("quality_status", "NEEDS_REVIEW"),
                    ("type_codes", "CASTLE"),
                ]
            )
        ),
    )
    nkp = create_place(
        session,
        PlaceInput.from_form(
            FormData(
                [
                    ("name", "NKP bez fotky"),
                    ("condition", "UNKNOWN"),
                    ("visitability", "UNKNOWN"),
                    ("heritage_status", "NKP"),
                    ("quality_status", "VERIFIED"),
                    ("type_codes", "CASTLE"),
                ]
            )
        ),
    )
    with_web = create_place(
        session,
        PlaceInput.from_form(
            FormData(
                [
                    ("name", "Se webem"),
                    ("condition", "UNKNOWN"),
                    ("visitability", "UNKNOWN"),
                    ("official_website", "https://example.test"),
                    ("quality_status", "VERIFIED"),
                    ("type_codes", "CASTLE"),
                ]
            )
        ),
    )

    worth = list_places(session, PlaceFilters(worth=True))
    assert {place.name for place in worth.places} == {"Zřícenina", "NKP bez fotky", "Se webem"}
    everything = list_places(session, PlaceFilters(worth=False))
    assert {place.name for place in everything.places} == {
        "Zřícenina",
        "Zaniklý",
        "Soukromý",
        "Neznámý",
        "NKP bez fotky",
        "Se webem",
    }
    counts = filter_facet_counts(session, PlaceFilters(worth=True))
    assert counts.worth == {"all": 6, "visit": 3}
    assert ruin.name == "Zřícenina"
    assert stub.name == "Neznámý"
    assert nkp.name == "NKP bez fotky"
    assert with_web.name == "Se webem"


def test_catalog_page_worth_toggle_defaults_to_visit(client) -> None:
    client.post("/places", data=_payload())
    client.post(
        "/places",
        data=_payload(
            name="Pustý zámek",
            condition="EXTINCT",
            visitability="EXTINCT",
            type_codes=["CASTLE"],
        ),
    )
    listing = client.get("/places")
    assert listing.status_code == 200
    assert "Bouzov" in listing.text
    assert "Pustý zámek" not in listing.text
    assert "Za návštěvu (1)" in listing.text
    assert "Vše (2)" in listing.text
    everything = client.get("/places?worth=all")
    assert "Pustý zámek" in everything.text
    assert 'name="worth" value="all"' in everything.text


def test_mark_ruins_free_access(session: Session) -> None:
    ruin = create_place(
        session,
        PlaceInput.from_form(
            FormData(
                [
                    ("name", "Testhrad"),
                    ("condition", "UNKNOWN"),
                    ("visitability", "UNKNOWN"),
                    ("quality_status", "VERIFIED"),
                    ("type_codes", "RUIN"),
                ]
            )
        ),
    )
    by_condition = create_place(
        session,
        PlaceInput.from_form(
            FormData(
                [
                    ("name", "Zřícený zámek"),
                    ("condition", "RUIN"),
                    ("visitability", "UNKNOWN"),
                    ("quality_status", "VERIFIED"),
                    ("type_codes", "CHATEAU"),
                ]
            )
        ),
    )
    extinct = create_place(
        session,
        PlaceInput.from_form(
            FormData(
                [
                    ("name", "Zaniklý hrad"),
                    ("condition", "EXTINCT"),
                    ("visitability", "UNKNOWN"),
                    ("quality_status", "VERIFIED"),
                    ("type_codes", "RUIN"),
                ]
            )
        ),
    )
    castle = create_place(
        session,
        PlaceInput.from_form(
            FormData(
                [
                    ("name", "Bouzov"),
                    ("condition", "PRESERVED"),
                    ("visitability", "UNKNOWN"),
                    ("quality_status", "VERIFIED"),
                    ("type_codes", "CASTLE"),
                ]
            )
        ),
    )
    private = create_place(
        session,
        PlaceInput.from_form(
            FormData(
                [
                    ("name", "Soukromá zřícenina"),
                    ("condition", "RUIN"),
                    ("visitability", "PRIVATE"),
                    ("quality_status", "VERIFIED"),
                    ("type_codes", "RUIN"),
                ]
            )
        ),
    )
    kept = create_place(
        session,
        PlaceInput.from_form(
            FormData(
                [
                    ("name", "Ručně neznámá"),
                    ("condition", "RUIN"),
                    ("visitability", "UNKNOWN"),
                    ("quality_status", "VERIFIED"),
                    ("type_codes", "RUIN"),
                ]
            )
        ),
    )
    upsert_override(session, kept, "visitability", "UNKNOWN", note="test")
    session.commit()

    assert mark_ruins_free_access(session) == 2
    session.refresh(ruin)
    session.refresh(by_condition)
    session.refresh(extinct)
    session.refresh(castle)
    session.refresh(private)
    session.refresh(kept)
    assert ruin.visitability == "FREE_ACCESS"
    assert by_condition.visitability == "FREE_ACCESS"
    assert extinct.visitability == "UNKNOWN"
    assert castle.visitability == "UNKNOWN"
    assert private.visitability == "PRIVATE"
    assert kept.visitability == "UNKNOWN"
    assert mark_ruins_free_access(session) == 0
