from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.datastructures import FormData

from app.db.models import PlaceSource
from app.importers.official_web.importer import records_for_places
from app.importers.official_web.parser import classify_html, skip_website
from app.services.apply_import import apply_import
from app.services.matching import LEVEL_A, match_record
from app.services.places import PlaceInput, create_place


BLATNA_HTML = """
<html><body>
  <a href="/visit/opening-hours">Otevírací doba</a>
  <a href="/visit">Prohlídky zámku</a>
  <p>Koupit vstupenku</p>
</body></html>
"""


def test_skip_commercial_catalogs() -> None:
    assert skip_website("https://www.hrady.cz/zamek-blatna")
    assert skip_website("https://www.kudyznudy.cz/aktivity/zamek")
    assert skip_website("https://cs.wikipedia.org/wiki/Blatn%C3%A1_(z%C3%A1mek)")
    assert not skip_website("https://www.zamek-blatna.cz/")


def test_classify_html_finds_visitor_signals() -> None:
    hint = classify_html(BLATNA_HTML, base_url="https://www.zamek-blatna.cz/")
    assert hint.visitability == "REGULAR"
    assert hint.opening_hours_url == "https://www.zamek-blatna.cz/visit/opening-hours"
    empty = classify_html("<html><body>Historie rodu</body></html>", base_url="https://example.cz/")
    assert empty.visitability is None


def test_official_web_updates_unknown_place(session: Session) -> None:
    place = create_place(
        session,
        PlaceInput.from_form(
            FormData(
                [
                    ("name", "Blatná"),
                    ("condition", "UNKNOWN"),
                    ("visitability", "UNKNOWN"),
                    ("quality_status", "VERIFIED"),
                    ("official_website", "https://www.zamek-blatna.cz/"),
                ]
            )
        ),
    )
    session.add(PlaceSource(place_id=place.id, source_type="wikidata", external_id="Q2240326"))
    session.commit()
    session.refresh(place)

    records = records_for_places(
        [place],
        fetch_html=lambda _url: BLATNA_HTML,
        fetched_at="2026-08-16T21:00:00+02:00",
    )
    assert len(records) == 1
    assert records[0].visitability == "REGULAR"
    assert records[0].allow_create is False
    assert match_record(session, records[0]).level == LEVEL_A
    result = apply_import(session, records, "official_web", make_backup=True)
    assert result.records_created == 0
    session.refresh(place)
    assert place.visitability == "REGULAR"
    assert place.opening_hours_url == "https://www.zamek-blatna.cz/visit/opening-hours"
    source = session.scalar(
        select(PlaceSource).where(PlaceSource.place_id == place.id, PlaceSource.source_type == "official_web")
    )
    assert source is not None
    assert "HTML not stored" in (source.raw_data or "")


def test_official_web_skips_ruins(session: Session) -> None:
    place = create_place(
        session,
        PlaceInput.from_form(
            FormData(
                [
                    ("name", "Testhrad"),
                    ("condition", "UNKNOWN"),
                    ("visitability", "UNKNOWN"),
                    ("quality_status", "VERIFIED"),
                    ("official_website", "https://www.testhrad.cz/"),
                    ("type_codes", "RUIN"),
                ]
            )
        ),
    )
    records = records_for_places([place], fetch_html=lambda _url: BLATNA_HTML)
    assert records == []
