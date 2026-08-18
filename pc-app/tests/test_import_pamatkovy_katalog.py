from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Place, PlaceSource
from app.importers.pamatkovy_katalog.importer import SAMPLE_CSV, records_from_csv_file
from app.importers.pamatkovy_katalog.parser import is_castle_like, records_from_tables
from app.importers.wikidata.importer import SAMPLE_SPARQL_FIXTURE, records_from_file as wikidata_records
from app.services.apply_import import apply_import
from app.services.matching import LEVEL_A, LEVEL_B, LEVEL_D, match_record


def test_castle_like_filter_and_parser() -> None:
    assert is_castle_like("hrad Bouzov")
    assert is_castle_like("zámek Hluboká")
    assert is_castle_like("rozhledna Cibulka")
    assert is_castle_like("Koněpruské jeskyně")
    assert not is_castle_like("sokolovna")
    records = records_from_csv_file(SAMPLE_CSV, fetched_at="2026-08-14T22:00:00+02:00")
    names = {item.name for item in records}
    assert "hrad Bouzov" in names
    assert "sokolovna" not in names
    bouzov = next(item for item in records if item.external_ids.get("uskp") == "19895/8-2468")
    assert bouzov.source_type == "pamatkovy_katalog"
    assert bouzov.external_id == "1000131753"
    assert bouzov.heritage_status == "NKP"
    assert bouzov.license == "CC BY 4.0"
    assert bouzov.municipality == "Bouzov"
    assert "Gotický hrad" in (bouzov.short_description or "")


def test_glued_obec_okres_takes_first_part() -> None:
    tables = {
        "KP": [
            {
                "katalogové_číslo": "1000158360",
                "název": "zámek Uherčice",
                "obec": "Brno; Milotice; Uherčice",
                "okres": "Brno-město; Hodonín; Znojmo",
                "kraj": "Jihomoravský kraj",
                "typ_památkové_ochrany": "kulturní památka",
                "rejstříkové_číslo_ÚSKP": "283",
                "anotace": "x",
            }
        ]
    }
    records = records_from_tables(tables, "t")
    assert len(records) == 1
    assert records[0].municipality == "Brno"
    assert records[0].district == "Brno-město"
    assert ";" not in (records[0].municipality or "")
    assert records[0].raw.get("glued_location") is True


def test_known_uskp_keeps_non_castle_row() -> None:
    tables = {
        "KP": [
            {
                "katalogové_číslo": "1",
                "název": "sokolovna",
                "obec": "Prostějov",
                "okres": "Prostějov",
                "kraj": "Olomoucký kraj",
                "typ_památkové_ochrany": "kulturní památka",
                "rejstříkové_číslo_ÚSKP": "100948",
                "anotace": "x",
            }
        ]
    }
    skipped = records_from_tables(tables, "t")
    assert skipped == []
    kept = records_from_tables(tables, "t", known_uskp={"100948"})
    assert len(kept) == 1
    assert kept[0].external_ids["uskp"] == "100948"


def test_wikidata_uskp_joins_katalog_level_a_keeps_public_id(session: Session) -> None:
    wiki = wikidata_records(SAMPLE_SPARQL_FIXTURE, fetched_at="2026-08-14T21:00:00+02:00")
    first = apply_import(session, wiki, "wikidata", make_backup=True)
    assert first.records_created == 6
    bouzov = session.scalar(select(Place).where(Place.name == "Bouzov"))
    assert bouzov is not None
    public_id = bouzov.public_id
    place_count = session.scalar(select(func.count()).select_from(Place))

    catalog = records_from_csv_file(SAMPLE_CSV, fetched_at="2026-08-14T22:00:00+02:00")
    matching = next(item for item in catalog if item.external_ids.get("uskp") == "19895/8-2468")
    decision = match_record(session, matching)
    assert decision.level == LEVEL_A
    assert decision.place is not None
    assert decision.place.public_id == public_id

    result = apply_import(session, catalog, "pamatkovy_katalog", make_backup=True)
    assert result.records_created == 0
    session.refresh(bouzov)
    assert bouzov.public_id == public_id
    assert session.scalar(select(func.count()).select_from(Place)) == place_count
    catalog_source = session.scalar(
        select(PlaceSource).where(
            PlaceSource.source_type == "pamatkovy_katalog",
            PlaceSource.external_id == "1000131753",
        )
    )
    assert catalog_source is not None
    assert catalog_source.place_id == bouzov.id
    assert catalog_source.license == "CC BY 4.0"
    assert bouzov.heritage_status == "NKP"


def test_katalog_same_name_same_municipality_without_gps_merges(session: Session) -> None:
    wiki = wikidata_records(SAMPLE_SPARQL_FIXTURE, fetched_at="t")
    apply_import(session, wiki, "wikidata", make_backup=True)
    catalog = records_from_csv_file(SAMPLE_CSV, fetched_at="t")
    unclear = next(item for item in catalog if item.external_id == "1000888888")
    decision = match_record(session, unclear)
    assert decision.level == LEVEL_B
    result = apply_import(session, [unclear], "pamatkovy_katalog", make_backup=True)
    assert result.records_created == 0
    assert result.records_updated == 1
    bouzov = session.scalar(select(Place).where(Place.name == "Bouzov"))
    assert bouzov is not None
    source = session.scalar(
        select(PlaceSource).where(PlaceSource.external_id == "1000888888")
    )
    assert source is not None
    assert source.place_id == bouzov.id


def test_repeated_katalog_import_zero_duplicates(session: Session) -> None:
    catalog = records_from_csv_file(SAMPLE_CSV, fetched_at="t")
    first = apply_import(session, catalog, "pamatkovy_katalog", make_backup=True)
    ids = {row.public_id for row in session.scalars(select(Place)).all()}
    second = apply_import(session, catalog, "pamatkovy_katalog", make_backup=True)
    assert second.records_created == 0
    assert second.counts_ok()
    again = {row.public_id for row in session.scalars(select(Place)).all()}
    assert again == ids
    catalog_ids = [
        row.external_id
        for row in session.scalars(
            select(PlaceSource).where(PlaceSource.source_type == "pamatkovy_katalog")
        ).all()
    ]
    assert len(catalog_ids) == len(set(catalog_ids))
    assert first.records_created >= 1


def test_cadastral_alias_does_not_match_other_palace(session: Session) -> None:
    from app.importers.base import CanonicalRecord

    existing = Place(
        name="Přemyslovský palác",
        municipality="Olomouc",
        alternative_names='["62746, Olomouc I, retrodíl hist. osady; 11412, Olomouc, město statutární"]',
        condition="UNKNOWN",
        visitability="UNKNOWN",
    )
    session.add(existing)
    session.commit()
    incoming = CanonicalRecord.from_dict(
        {
            "source_type": "pamatkovy_katalog",
            "external_id": "1000123614",
            "name": "arcibiskupský palác",
            "alternative_names": [
                "62746, Olomouc I, retrodíl hist. osady; 11412, Olomouc, město statutární"
            ],
            "types": ["PALACE"],
            "municipality": "Olomouc",
            "fetched_at": "2026-08-16T22:00:00+02:00",
        }
    )
    decision = match_record(session, incoming)
    assert decision.level == LEVEL_D
