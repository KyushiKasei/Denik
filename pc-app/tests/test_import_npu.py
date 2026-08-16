from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Place, PlaceSource
from app.importers.npu.client import build_managed_query
from app.importers.npu.importer import SAMPLE_JSON, records_from_file
from app.importers.npu.parser import visitor_urls
from app.importers.wikidata.importer import SAMPLE_SPARQL_FIXTURE, records_from_file as wikidata_records
from app.services.apply_import import apply_import
from app.services.matching import LEVEL_A, match_record


def test_visitor_urls_are_links_not_scraped_html() -> None:
    hours, tickets = visitor_urls("https://www.hrad-karlstejn.cz/")
    assert hours is not None and hours.endswith("/navstevni-doba")
    assert tickets is not None and tickets.endswith("/vstupne")
    assert visitor_urls("https://www.npu.cz/") == (None, None)


def test_npu_query_includes_regional_offices() -> None:
    query = build_managed_query()
    assert "wd:Q12039181" in query
    assert "wdt:P749" in query
    assert "wdt:P361" in query
    assert "wdt:P127" in query


def test_npu_managed_joins_wikidata_keeps_public_id(session: Session) -> None:
    wiki = wikidata_records(SAMPLE_SPARQL_FIXTURE, fetched_at="t")
    apply_import(session, wiki, "wikidata", make_backup=True)
    bouzov = session.scalar(select(Place).where(Place.name == "Bouzov"))
    assert bouzov is not None
    public_id = bouzov.public_id
    records = records_from_file(SAMPLE_JSON, fetched_at="t")
    assert all(item.short_description is None for item in records)
    decision = match_record(session, records[0])
    assert decision.level == LEVEL_A
    result = apply_import(session, records, "npu", make_backup=True)
    assert result.records_created == 0
    session.refresh(bouzov)
    assert bouzov.public_id == public_id
    assert bouzov.opening_hours_url and "navstevni-doba" in bouzov.opening_hours_url
    assert bouzov.ticket_url and "vstupne" in bouzov.ticket_url
    assert bouzov.visitability == "REGULAR"
    source = session.scalar(
        select(PlaceSource).where(PlaceSource.source_type == "npu", PlaceSource.external_id == "hrad-bouzov.cz")
    )
    assert source is not None
    assert source.place_id == bouzov.id
    assert "URL only" in (source.license or "")
    assert session.scalar(select(func.count()).select_from(Place)) == 6

    second = apply_import(session, records, "npu", make_backup=True)
    assert second.records_created == 0
