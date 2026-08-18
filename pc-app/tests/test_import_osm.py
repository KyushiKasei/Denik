from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Place, PlaceSource
from app.importers.base import CanonicalRecord
from app.importers.osm.importer import SAMPLE_JSON, records_from_file
from app.importers.osm.client import QUERY, OsmClient
from app.importers.osm.parser import (
    address_from_tags,
    amenities_from_tags,
    condition_from_tags,
    dogs_from_tags,
    municipality_from_tags,
    payment_from_tags,
    types_from_tags,
    visitability_from_tags,
)
from app.importers.wikidata.importer import SAMPLE_SPARQL_FIXTURE, records_from_file as wikidata_records
from app.services.apply_import import apply_import
from app.services.matching import LEVEL_A, match_record


def test_osm_matches_wikidata_tag_and_is_optional_supplement(session: Session) -> None:
    wiki = wikidata_records(SAMPLE_SPARQL_FIXTURE, fetched_at="t")
    apply_import(session, wiki, "wikidata", make_backup=True)
    bouzov = session.scalar(select(Place).where(Place.name == "Bouzov"))
    assert bouzov is not None
    public_id = bouzov.public_id
    records = records_from_file(SAMPLE_JSON, fetched_at="t")
    tagged = next(item for item in records if item.external_ids.get("wikidata") == "Q122922")
    assert tagged.external_id == "way/123456"
    assert match_record(session, tagged).level == LEVEL_A
    result = apply_import(session, records, "osm", make_backup=True)
    session.refresh(bouzov)
    assert bouzov.public_id == public_id
    source = session.scalar(
        select(PlaceSource).where(PlaceSource.source_type == "osm", PlaceSource.external_id == "way/123456")
    )
    assert source is not None
    assert source.place_id == bouzov.id
    assert source.license == "ODbL"
    extra = session.scalar(select(Place).where(Place.name == "Hrad BezWikidat"))
    assert extra is not None
    assert extra.municipality == "Praha"
    assert result.records_created == 1
    session.refresh(bouzov)
    assert bouzov.osm_opening_hours == "Mo-Su 09:00-16:00"
    assert bouzov.phone == "+420 585 346 201"
    assert bouzov.fee == "yes"
    assert bouzov.wheelchair == "limited"
    assert bouzov.parking == "yes"
    assert bouzov.visit_duration_minutes == 90
    assert bouzov.dogs == "no"
    assert bouzov.payment == "cash"
    assert "toilets" in bouzov.amenity_codes
    assert "cafe" in bouzov.amenity_codes
    second = apply_import(session, records, "osm", make_backup=True)
    assert second.records_created == 0
    assert session.scalar(select(func.count()).select_from(Place).where(Place.name == "Bouzov")) == 1


def test_osm_opening_hours_truncated_to_500() -> None:
    from app.importers.osm.parser import records_from_overpass

    hours = "Mo-Su 09:00-17:00; " + ("PH off; " * 80)
    assert len(hours) > 500
    payload = {
        "elements": [
            {
                "type": "way",
                "id": 1,
                "lat": 50.0,
                "lon": 14.4,
                "tags": {"historic": "castle", "name": "Dlouhé hodiny", "opening_hours": hours},
            }
        ]
    }
    records = records_from_overpass(payload, "t")
    assert records
    assert records[0].osm_opening_hours is not None
    assert len(records[0].osm_opening_hours) == 500
    assert '["historic"="castle"]' in QUERY
    assert '["tower:type"="observation"]' in QUERY
    assert '["tourism"="zoo"]' in QUERY
    assert '["natural"="cave_entrance"]' in QUERY
    assert '["amenity"="toilets"]' in QUERY
    assert '["amenity"="cafe"]' in QUERY
    assert '["leisure"="playground"]' in QUERY
    assert "around.heritage:350" in QUERY
    assert "[timeout:120]" in QUERY
    assert OsmClient().timeout >= 120


def test_osm_dogs_payment_amenities_from_tags() -> None:
    assert dogs_from_tags({"dogs": "leashed"}) == "leashed"
    assert dogs_from_tags({"dog": "no"}) == "no"
    assert payment_from_tags({"payment:cash": "yes"}) == "cash"
    assert payment_from_tags({"payment:cash": "yes", "payment:credit_cards": "yes"}) == "cash_and_cards"
    assert amenities_from_tags({"toilets": "yes", "leisure": "playground"}) == ["toilets", "playground"]
    assert amenities_from_tags({"amenity": "cafe"}) == ["cafe"]


def test_osm_types_from_tags() -> None:
    assert types_from_tags({"tourism": "zoo"}) == ["ZOO"]
    assert types_from_tags({"natural": "cave_entrance"}) == ["CAVE"]
    assert types_from_tags({"man_made": "tower", "tower:type": "observation"}) == ["LOOKOUT_TOWER"]
    assert types_from_tags({"historic": "castle"}) == ["CASTLE"]
    assert types_from_tags({"historic": "castle", "ruins": "yes"}) == ["RUIN"]


def test_osm_address_and_municipality_from_tags() -> None:
    assert municipality_from_tags({"addr:village": "Dolní Adršpach", "addr:city": "Adršpach"}) == "Adršpach"
    assert address_from_tags({"addr:place": "Dolní Adršpach", "addr:housenumber": "75"}) == "Dolní Adršpach 75"


def test_osm_visitability_from_tags() -> None:
    assert visitability_from_tags({"opening_hours": "Mo-Su 09:00-16:00"}) == "REGULAR"
    assert visitability_from_tags({"opening_hours": "Apr-Oct Mo-Su 09:00-17:00"}) == "SEASONAL"
    assert visitability_from_tags({"tourism": "attraction"}) == "REGULAR"
    assert visitability_from_tags({"tourism": "zoo"}) == "REGULAR"
    assert visitability_from_tags({"fee": "yes"}) == "REGULAR"
    assert visitability_from_tags({"fee": "no"}) == "FREE_ACCESS"
    assert visitability_from_tags({"access": "private"}) == "PRIVATE"
    assert visitability_from_tags({"access": "customers"}) == "REGULAR"
    assert visitability_from_tags({"ruins": "yes"}) == "FREE_ACCESS"
    assert visitability_from_tags({"ruins": "yes", "access": "private"}) == "PRIVATE"
    assert visitability_from_tags({"website": "https://www.zamek-blatna.cz/"}) is None


def test_osm_condition_from_tags() -> None:
    assert condition_from_tags({"ruins": "yes"}) == "RUIN"
    assert condition_from_tags({"historic": "ruins"}) == "RUIN"
    assert condition_from_tags({"historic": "archaeological_site"}) == "REMAINS"
    assert condition_from_tags({"demolished": "yes"}) == "EXTINCT"
    assert condition_from_tags({"demolished:building": "yes"}) == "EXTINCT"
    assert condition_from_tags({"destroyed": "yes", "ruins": "yes"}) == "EXTINCT"
    assert condition_from_tags({"historic": "castle"}) is None


def test_osm_does_not_overwrite_wikidata_condition(session: Session) -> None:
    wiki = CanonicalRecord(
        source_type="wikidata",
        external_id="Q900001",
        external_ids={"wikidata": "Q900001"},
        name="Zaniklý Test",
        types=["CASTLE"],
        condition="EXTINCT",
        latitude=50.0,
        longitude=14.0,
        fetched_at="t",
    )
    apply_import(session, [wiki], "wikidata", make_backup=True)
    osm = CanonicalRecord(
        source_type="osm",
        external_id="node/1",
        external_ids={"osm": "node/1", "wikidata": "Q900001"},
        name="Zaniklý Test",
        types=["RUIN"],
        condition="RUIN",
        latitude=50.0,
        longitude=14.0,
        fetched_at="t",
    )
    apply_import(session, [osm], "osm", make_backup=True)
    place = session.scalar(select(Place).where(Place.name == "Zaniklý Test"))
    assert place is not None
    assert place.condition == "EXTINCT"
