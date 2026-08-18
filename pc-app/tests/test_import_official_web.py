from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.datastructures import FormData

from app.db.models import PlaceSource
from app.importers.official_web.importer import can_enrich_place, records_for_places
from app.importers.official_web.parser import classify_html, parse_public_ids, skip_website
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

JSONLD_HTML = """
<html><body>
<script type="application/ld+json">
{"@type":"TouristAttraction","name":"Blatná","openingHours":"Mo-Su 09:00-16:00",
 "offers":{"@type":"Offer","url":"https://www.zamek-blatna.cz/vstupne"}}
</script>
</body></html>
"""

ATTRACTION_ONLY_HTML = """
<html><body>
<script type="application/ld+json">
{"@type":"TouristAttraction","name":"Bouzov"}
</script>
</body></html>
"""

TICKET_HREF_HTML = """
<html><body>
  <a href="/cs/informace-pro-navstevniky/vstupne">Vstupné</a>
  <p>Prohlídky zámku</p>
</body></html>
"""


def _place(session: Session, **fields: str) -> Place:
    payload = [
        ("name", fields.get("name", "Blatná")),
        ("condition", fields.get("condition", "UNKNOWN")),
        ("visitability", fields.get("visitability", "UNKNOWN")),
        ("quality_status", "VERIFIED"),
        ("official_website", fields.get("official_website", "https://www.zamek-blatna.cz/")),
    ]
    if "type_codes" in fields:
        payload.append(("type_codes", fields["type_codes"]))
    place = create_place(session, PlaceInput.from_form(FormData(payload)))
    if fields.get("wikidata"):
        session.add(PlaceSource(place_id=place.id, source_type="wikidata", external_id=fields["wikidata"]))
        session.commit()
        session.refresh(place)
    return place


def test_skip_commercial_catalogs() -> None:
    assert skip_website("https://www.hrady.cz/zamek-blatna")
    assert skip_website("https://www.kudyznudy.cz/aktivity/zamek")
    assert skip_website("https://cs.wikipedia.org/wiki/Blatn%C3%A1_(z%C3%A1mek)")
    assert not skip_website("https://www.zamek-blatna.cz/")


def test_parse_public_ids() -> None:
    assert parse_public_ids(" a,b\nc ") == ["a", "b", "c"]
    assert parse_public_ids("  ") == []


def test_classify_html_finds_visitor_signals() -> None:
    hint = classify_html(BLATNA_HTML, base_url="https://www.zamek-blatna.cz/")
    assert hint.visitability == "REGULAR"
    assert hint.opening_hours_url == "https://www.zamek-blatna.cz/visit/opening-hours"
    assert hint.ticket_url is None
    empty = classify_html("<html><body>Historie rodu</body></html>", base_url="https://example.cz/")
    assert empty.visitability is None
    assert empty.opening_hours_url is None
    assert empty.ticket_url is None


def test_classify_html_jsonld_hours_and_tickets() -> None:
    hint = classify_html(JSONLD_HTML, base_url="https://www.zamek-blatna.cz/")
    assert hint.visitability == "REGULAR"
    assert hint.opening_hours_url == "https://www.zamek-blatna.cz/"
    assert hint.ticket_url == "https://www.zamek-blatna.cz/vstupne"


def test_classify_html_ticket_href() -> None:
    hint = classify_html(TICKET_HREF_HTML, base_url="https://www.zamek-blatna.cz/")
    assert hint.visitability == "REGULAR"
    assert hint.ticket_url == "https://www.zamek-blatna.cz/cs/informace-pro-navstevniky/vstupne"


def test_official_web_updates_unknown_place(session: Session) -> None:
    place = _place(session, wikidata="Q2240326")
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
    assert "<html" not in (source.raw_data or "")


def test_official_web_skips_ruins(session: Session) -> None:
    place = _place(session, name="Testhrad", official_website="https://www.testhrad.cz/", type_codes="RUIN")
    records = records_for_places([place], fetch_html=lambda _url: BLATNA_HTML)
    assert records == []
    assert not can_enrich_place(place)


def test_official_web_skips_hrady_host(session: Session) -> None:
    place = _place(session, official_website="https://www.hrady.cz/zamek-blatna")
    records = records_for_places([place], fetch_html=lambda _url: BLATNA_HTML)
    assert records == []


def test_bulk_fills_regular_place_missing_urls(session: Session) -> None:
    place = _place(session, visitability="REGULAR", wikidata="Q2240326")
    records = records_for_places([place], fetch_html=lambda _url: JSONLD_HTML)
    assert len(records) == 1
    result = apply_import(session, records, "official_web", make_backup=True)
    assert result.records_created == 0
    session.refresh(place)
    assert place.visitability == "REGULAR"
    assert place.opening_hours_url == "https://www.zamek-blatna.cz/"
    assert place.ticket_url == "https://www.zamek-blatna.cz/vstupne"


def test_bulk_skips_regular_place_with_urls(session: Session) -> None:
    place = _place(session, visitability="REGULAR", wikidata="Q2240326")
    place.opening_hours_url = "https://www.zamek-blatna.cz/hodiny"
    place.ticket_url = "https://www.zamek-blatna.cz/vstupne"
    session.commit()
    skipped = records_for_places([place], fetch_html=lambda _url: JSONLD_HTML)
    assert skipped == []
    records = records_for_places([place], fetch_html=lambda _url: JSONLD_HTML, selected=True)
    assert len(records) == 1


def test_npu_convention_404_not_stored(session: Session) -> None:
    place = _place(
        session,
        name="Bouzov",
        visitability="REGULAR",
        official_website="https://www.hrad-bouzov.cz/",
        wikidata="Q122922",
    )

    def fetch(url: str) -> str | None:
        if "navstevni-doba" in url or url.rstrip("/").endswith("vstupne"):
            return None
        return ATTRACTION_ONLY_HTML

    records = records_for_places([place], fetch_html=fetch, selected=True, check_url=fetch)
    assert len(records) == 1
    assert records[0].opening_hours_url is None
    assert records[0].ticket_url is None
    apply_import(session, records, "official_web", make_backup=True)
    session.refresh(place)
    assert place.opening_hours_url is None
    assert place.ticket_url is None
    source = session.scalar(
        select(PlaceSource).where(PlaceSource.place_id == place.id, PlaceSource.source_type == "official_web")
    )
    assert source is not None
    assert "<html" not in (source.raw_data or "")


def test_npu_convention_200_sets_urls(session: Session) -> None:
    place = _place(
        session,
        name="Bouzov",
        visitability="REGULAR",
        official_website="https://www.hrad-bouzov.cz/",
        wikidata="Q122922",
    )

    def fetch(url: str) -> str | None:
        if "navstevni-doba" in url or url.rstrip("/").endswith("vstupne"):
            return "<html><body><nav>ok</nav></body></html>"
        return ATTRACTION_ONLY_HTML

    records = records_for_places([place], fetch_html=fetch, selected=True, check_url=fetch)
    assert records[0].opening_hours_url == "https://www.hrad-bouzov.cz/cs/informace-pro-navstevniky/navstevni-doba"
    assert records[0].ticket_url == "https://www.hrad-bouzov.cz/cs/informace-pro-navstevniky/vstupne"


def test_detail_has_enrich_button(client) -> None:
    created = client.post(
        "/places",
        data={
            "name": "Blatná",
            "condition": "PRESERVED",
            "visitability": "REGULAR",
            "quality_status": "VERIFIED",
            "country": "CZ",
            "official_website": "https://www.zamek-blatna.cz/",
            "type_codes": ["CHATEAU"],
        },
        follow_redirects=False,
    )
    assert created.status_code == 303
    location = created.headers["location"]
    public_id = location.split("/places/")[1].split("?")[0]
    detail = client.get(f"/places/{public_id}")
    assert "Doplnit z oficiálního webu" in detail.text
    assert public_id in detail.text
    page = client.get("/import")
    assert 'name="public_ids"' in page.text
