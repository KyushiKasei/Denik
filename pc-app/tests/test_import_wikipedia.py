from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Place, PlaceSource
from app.importers.wikidata.importer import SAMPLE_SPARQL_FIXTURE, records_from_file as wikidata_records
from app.importers.wikipedia.importer import SAMPLE_JSON, records_from_file
from app.importers.wikipedia.parser import CATEGORIES, type_from_category
from app.services.apply_import import apply_import
from app.services.matching import LEVEL_A, match_record


def test_wikipedia_categories_include_lookout_and_zoo() -> None:
    assert "Kategorie:Rozhledny_v_Česku" in CATEGORIES
    assert "Kategorie:Zoologické_zahrady_v_Česku" in CATEGORIES
    assert "Kategorie:Jeskyně_v_Česku" in CATEGORIES
    assert type_from_category("Kategorie:Rozhledny_v_Česku") == ["LOOKOUT_TOWER"]
    assert type_from_category("Kategorie:Zoologické_zahrady_v_Česku") == ["ZOO"]
    assert type_from_category("Kategorie:Jeskyně_v_Česku") == ["CAVE"]
    assert type_from_category("Kategorie:Hrady_v_Česku") == ["CASTLE"]
    assert type_from_category("Kategorie:Hrady v Česku") == ["CASTLE"]


def test_wikipedia_url_only_joins_qid_and_flags_missing(session: Session) -> None:
    wiki = wikidata_records(SAMPLE_SPARQL_FIXTURE, fetched_at="t")
    apply_import(session, wiki, "wikidata", make_backup=True)
    bouzov = session.scalar(select(Place).where(Place.name == "Bouzov"))
    assert bouzov is not None
    public_id = bouzov.public_id
    records = records_from_file(SAMPLE_JSON, fetched_at="t")
    assert all(item.short_description is None for item in records)
    assert all(item.raw.get("extract") is None for item in records)
    bouzov_rec = next(item for item in records if "Q122922" in item.external_ids.values())
    assert match_record(session, bouzov_rec).level == LEVEL_A
    result = apply_import(session, records, "wikipedia", make_backup=True)
    session.refresh(bouzov)
    assert bouzov.public_id == public_id
    assert "wikipedia.org" in (bouzov.wikipedia_url or "")
    source = session.scalar(
        select(PlaceSource).where(PlaceSource.source_type == "wikipedia", PlaceSource.external_id.like("cs:Bouzov%"))
    )
    assert source is not None
    assert source.place_id == bouzov.id
    missing = session.scalar(select(Place).where(Place.name == "Hrad Neznámý"))
    assert missing is not None
    assert missing.wikipedia_url
    assert result.records_created == 1
    second = apply_import(session, records, "wikipedia", make_backup=True)
    assert second.records_created == 0
    assert session.scalar(select(Place).where(Place.name == "Hrad Neznámý")) is not None
