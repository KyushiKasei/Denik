from __future__ import annotations

import httpx
import pytest
from sqlalchemy.orm import Session

from app.db.models import Place, PlaceJournalState, Visit
from app.ids import new_public_id
from app.services.geo import DEFAULT_RADIUS_KM, MAX_RADIUS_KM, MIN_RADIUS_KM, clamp_radius_km, distance_m, haversine_km
from app.services.nearby import (
    geocode_nominatim,
    list_nearby,
    resolve_origin_from_catalog,
    suggest_origins,
)
from app.services.places import PlaceInput, create_place

# Bouzov (49.704, 16.891) ↔ bod ~10 km východně: stejný vzorec jako matching.distance_m.
BOUZOV = (49.704, 16.891)
EAST = (49.704, 17.03)


def _place(session: Session, **overrides) -> Place:
    data = PlaceInput(
        name="Bouzov",
        condition="PRESERVED",
        visitability="REGULAR",
        quality_status="VERIFIED",
        municipality="Bouzov",
        district="Olomouc",
        region="Olomoucký kraj",
        latitude=BOUZOV[0],
        longitude=BOUZOV[1],
        type_codes=["CASTLE"],
    )
    for key, value in overrides.items():
        setattr(data, key, value)
    return create_place(session, data)


def test_haversine_matches_matching_meters() -> None:
    km = haversine_km(*BOUZOV, *EAST)
    meters = distance_m(*BOUZOV, *EAST)
    assert km is not None and meters is not None
    assert km == pytest.approx(meters / 1000.0)
    assert 9.0 < km < 12.0


def test_haversine_none_without_gps() -> None:
    assert haversine_km(None, 16.8, 49.7, 16.8) is None
    assert haversine_km(49.7, 16.8, None, 16.8) is None


def test_clamp_radius() -> None:
    assert clamp_radius_km(None) == DEFAULT_RADIUS_KM
    assert clamp_radius_km("30") == 30
    assert clamp_radius_km(1) == MIN_RADIUS_KM
    assert clamp_radius_km(999) == MAX_RADIUS_KM
    assert clamp_radius_km("x") == DEFAULT_RADIUS_KM


def test_nearby_orders_by_distance_and_respects_radius(session: Session) -> None:
    bouzov = _place(session)
    near = _place(session, name="Blízko", municipality="Loštice", latitude=EAST[0], longitude=EAST[1])
    far = _place(
        session,
        name="Praha",
        municipality="Praha",
        district="Praha",
        region="Hlavní město Praha",
        latitude=50.087,
        longitude=14.421,
        type_codes=["PALACE"],
    )
    missing = _place(session, name="Bez GPS", latitude=None, longitude=None)

    from app.services.nearby import Origin

    origin = Origin(latitude=BOUZOV[0], longitude=BOUZOV[1], label="tady", source="coords")
    result = list_nearby(session, origin, radius_km=30)
    names = [hit.place.name for hit in result.hits]
    assert names[0] == "Bouzov"
    assert "Blízko" in names
    assert "Praha" not in names
    assert "Bez GPS" not in names
    assert result.skipped_no_gps == 1
    assert result.hits[0].km < result.hits[1].km
    assert all(hit.km <= 30 for hit in result.hits)

    tight = list_nearby(session, origin, radius_km=5)
    assert [hit.place.name for hit in tight.hits] == ["Bouzov"]
    assert bouzov.public_id == tight.hits[0].place.public_id
    assert near.public_id not in {hit.place.public_id for hit in tight.hits}
    assert far.archived_at is None
    assert missing.latitude is None


def test_nearby_type_filter(session: Session) -> None:
    _place(session)
    _place(
        session,
        name="Zámek",
        type_codes=["CHATEAU"],
        latitude=49.71,
        longitude=16.90,
    )
    from app.services.nearby import Origin

    origin = Origin(latitude=BOUZOV[0], longitude=BOUZOV[1], label="tady", source="coords")
    only_castle = list_nearby(session, origin, radius_km=30, type_code="CASTLE")
    assert [hit.place.name for hit in only_castle.hits] == ["Bouzov"]


def test_nearby_skips_archived(session: Session) -> None:
    from app.services.places import archive_place

    place = _place(session)
    archive_place(session, place)
    from app.services.nearby import Origin

    origin = Origin(latitude=BOUZOV[0], longitude=BOUZOV[1], label="tady", source="coords")
    result = list_nearby(session, origin, radius_km=30)
    assert result.hits == []


def test_nearby_not_visited_filter(session: Session) -> None:
    visited = _place(session)
    other = _place(session, name="Šternberk", latitude=49.73, longitude=17.00)
    session.add(
        Visit(
            public_id=new_public_id(),
            place_id=visited.id,
            place_public_id=visited.public_id,
            visited_at="2026-08-01",
        )
    )
    session.add(
        PlaceJournalState(
            place_public_id=other.public_id,
            place_id=other.id,
            want_to_visit=1,
        )
    )
    session.commit()
    from app.services.nearby import Origin

    origin = Origin(latitude=BOUZOV[0], longitude=BOUZOV[1], label="tady", source="coords")
    unseen = list_nearby(session, origin, radius_km=30, journal="not_visited")
    assert [hit.place.name for hit in unseen.hits] == ["Šternberk"]
    want = list_nearby(session, origin, radius_km=30, journal="want_to_visit")
    assert [hit.place.name for hit in want.hits] == ["Šternberk"]


def test_origin_from_place_and_municipality(session: Session) -> None:
    _place(session)
    origin = resolve_origin_from_catalog(session, "Bouzov")
    assert origin is not None
    assert origin.source == "place"
    assert origin.latitude == BOUZOV[0]
    muni = resolve_origin_from_catalog(session, "bouzov")
    assert muni is not None
    suggestions = suggest_origins(session, "Bou")
    assert any(item.label == "Bouzov" for item in suggestions)


def test_geocode_nominatim_uses_user_agent() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "PamatkyDenik" in request.headers.get("user-agent", "")
        assert request.headers.get("accept-language") == "cs"
        assert request.url.params.get("countrycodes") == "cz"
        body = [{"lat": "50.0755", "lon": "14.4378", "display_name": "Praha"}]
        return httpx.Response(200, json=body)

    transport = httpx.MockTransport(handler)
    origin = geocode_nominatim("Praha", transport=transport)
    assert origin is not None
    assert origin.source == "nominatim"
    assert origin.latitude == 50.0755


def test_nearby_page_lists_hits(client) -> None:
    client.post(
        "/places",
        data={
            "name": "Bouzov",
            "condition": "PRESERVED",
            "visitability": "REGULAR",
            "quality_status": "VERIFIED",
            "country": "CZ",
            "municipality": "Bouzov",
            "latitude": "49.704",
            "longitude": "16.891",
            "type_codes": ["CASTLE"],
        },
    )
    empty = client.get("/nearby")
    assert empty.status_code == 200
    assert "Poblíž" in empty.text
    assert "nearby-gps-error" in empty.text
    assert "map-legend" in empty.text
    assert "chci navštívit" in empty.text
    page = client.get("/nearby", params={"lat": "49.704", "lon": "16.891", "radius_km": "30"})
    assert page.status_code == 200
    assert "Bouzov" in page.text
    assert "v radiusu" in page.text
    assert 'id="nearby-map"' in page.text
    assert 'id="nearby-map-data"' in page.text
    nearby_js = client.get("/static/nearby.js").text
    assert "marker-icon.png" in nearby_js
    assert 'data.mode === "atlas"' in nearby_js
    assert "atlasTimeline" in nearby_js
    named = client.get("/nearby", params={"q": "Bouzov", "radius_km": "30"})
    assert named.status_code == 200
    assert "Bouzov" in named.text
    suggest = client.get("/nearby/suggest", params={"q": "Bou"})
    assert suggest.status_code == 200
    assert "Bouzov" in suggest.text


def test_nearby_caps_to_nearest(session: Session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.services.nearby.MAX_NEARBY_HITS", 1)
    _place(session, name="Tady")
    _place(session, name="Dál", latitude=EAST[0], longitude=EAST[1], municipality="Loštice")
    from app.services.nearby import Origin

    origin = Origin(latitude=BOUZOV[0], longitude=BOUZOV[1], label="tady", source="coords")
    result = list_nearby(session, origin, radius_km=30)
    assert result.hits_total == 2
    assert [hit.place.name for hit in result.hits] == ["Tady"]
