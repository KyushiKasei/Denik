from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Place, PlaceSource
from app.importers.osm.importer import SAMPLE_JSON, records_from_file
from app.importers.osm.client import QUERY
from app.importers.osm.parser import address_from_tags, municipality_from_tags, types_from_tags, visitability_from_tags
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
    second = apply_import(session, records, "osm", make_backup=True)
    assert second.records_created == 0
    assert session.scalar(select(func.count()).select_from(Place).where(Place.name == "Bouzov")) == 1


def test_osm_query_includes_lookout_and_zoo() -> None:
    assert '["historic"="castle"]' in QUERY
    assert '["tower:type"="observation"]' in QUERY
    assert '["tourism"="zoo"]' in QUERY
    assert '["natural"="cave_entrance"]' in QUERY


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
