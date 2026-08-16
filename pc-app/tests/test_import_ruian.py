from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Place, PlaceSource
from app.importers.ruian.importer import lookup_from_sample_dir, records_for_places
from app.importers.wikidata.importer import SAMPLE_SPARQL_FIXTURE, records_from_file
from app.services.apply_import import apply_import
from app.services.geo import ReverseLocation, parse_nominatim_address
from app.services.matching import LEVEL_A, match_record


def test_ruian_disambiguates_same_municipality_name() -> None:
    lookup = lookup_from_sample_dir()
    bouzov = lookup.match("Bouzov", "Olomouc")
    assert bouzov is not None
    assert bouzov.obec_kod == "505026"
    assert bouzov.okres_nazev == "Olomouc"
    assert bouzov.kraj_nazev == "Olomoucký kraj"
    assert lookup.match("Adamov") is None
    blansko = lookup.match("Adamov", "Blansko")
    kladno = lookup.match("Adamov", "Kladno")
    assert blansko is not None and kladno is not None
    assert blansko.obec_kod != kladno.obec_kod


def test_ruian_normalizes_existing_place_no_duplicate(session: Session) -> None:
    wiki = records_from_file(SAMPLE_SPARQL_FIXTURE, fetched_at="t")
    apply_import(session, wiki, "wikidata", make_backup=True)
    bouzov = session.scalar(select(Place).where(Place.name == "Bouzov"))
    assert bouzov is not None
    public_id = bouzov.public_id
    lookup = lookup_from_sample_dir()
    records = records_for_places([bouzov], lookup, fetched_at="2026-08-14T22:00:00+02:00")
    assert len(records) == 1
    assert records[0].allow_create is False
    assert records[0].municipality_code == "505026"
    decision = match_record(session, records[0])
    assert decision.level == LEVEL_A
    result = apply_import(session, records, "ruian", make_backup=True)
    assert result.records_created == 0
    session.refresh(bouzov)
    assert bouzov.public_id == public_id
    assert bouzov.municipality_code == "505026"
    assert bouzov.district_code == "3805"
    assert bouzov.region_code == "124"
    assert session.scalar(select(func.count()).select_from(Place)) == 6
    ruian_source = session.scalar(
        select(PlaceSource).where(PlaceSource.place_id == bouzov.id, PlaceSource.source_type == "ruian")
    )
    assert ruian_source is not None
    assert ruian_source.license == "CC BY 4.0"

    again = apply_import(session, records, "ruian", make_backup=True)
    assert again.records_created == 0
    ruian_count = session.scalar(
        select(func.count()).select_from(PlaceSource).where(
            PlaceSource.place_id == bouzov.id, PlaceSource.source_type == "ruian"
        )
    )
    assert ruian_count == 1
    wiki_source = session.scalar(
        select(PlaceSource).where(PlaceSource.place_id == bouzov.id, PlaceSource.source_type == "wikidata")
    )
    assert wiki_source is not None
    assert '"source_type": "wikidata"' in (wiki_source.raw_data or "")


def test_parse_nominatim_address_prefers_municipality_over_village() -> None:
    loc = parse_nominatim_address(
        {
            "address": {
                "house_number": "75",
                "village": "Dolní Adršpach",
                "municipality": "Adršpach",
                "county": "okres Náchod",
                "state": "Královéhradecký kraj",
            }
        }
    )
    assert loc is not None
    assert loc.municipality == "Adršpach"
    assert loc.village == "Dolní Adršpach"
    assert loc.district == "Náchod"
    assert loc.region == "Královéhradecký kraj"
    assert loc.address == "Dolní Adršpach 75"
    assert loc.municipality_candidates[0] == "Adršpach"


def test_ruian_fills_municipality_from_coordinates(session: Session) -> None:
    wiki = records_from_file(SAMPLE_SPARQL_FIXTURE, fetched_at="t")
    apply_import(session, wiki, "wikidata", make_backup=True)
    ruin = session.scalar(select(Place).where(Place.name == "Zřícenina Testhrad"))
    assert ruin is not None
    assert ruin.municipality is None
    public_id = ruin.public_id
    lookup = lookup_from_sample_dir()
    loc = ReverseLocation(
        municipality="Bouzov",
        district="Olomouc",
        region="Olomoucký kraj",
        address="Bouzov 1",
        municipality_candidates=("Dolní Adršpach", "Bouzov"),
    )
    records = records_for_places(
        [ruin],
        lookup,
        fetched_at="2026-08-14T22:00:00+02:00",
        reverse_fn=lambda _lat, _lon: loc,
    )
    assert len(records) == 1
    assert records[0].municipality == "Bouzov"
    assert records[0].municipality_code == "505026"
    result = apply_import(session, records, "ruian", make_backup=True)
    assert result.records_created == 0
    session.refresh(ruin)
    assert ruin.public_id == public_id
    assert ruin.municipality == "Bouzov"
    assert ruin.district == "Olomouc"
    assert ruin.address == "Bouzov 1"
