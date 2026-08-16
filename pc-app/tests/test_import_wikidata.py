from __future__ import annotations

from urllib.parse import unquote_plus

import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Place, PlacePhoto, PlaceSource
from app.importers.base import CanonicalRecord
from app.importers.wikidata.client import ENDPOINT, USER_AGENT, SparqlError, WikidataClient
from app.importers.wikidata.importer import SAMPLE_SPARQL_FIXTURE, fetch_summary, load_bundle_file, records_from_file
from app.importers.wikidata.parser import (
    compose_address,
    count_without_gps,
    image_from_p18,
    parse_sparql_response,
    parse_wkt_point,
    qid_from_uri,
    records_from_bundle,
)
from app.importers.wikidata.query import TYPE_CLASSES, build_query
from app.services.apply_import import apply_import


def _sample_records():
    return records_from_file(SAMPLE_SPARQL_FIXTURE, fetched_at="2026-08-14T21:00:00+02:00")


def _by_qid(records: list[CanonicalRecord]) -> dict[str, CanonicalRecord]:
    return {item.external_id: item for item in records}


def test_type_classes_include_lookout_zoo_and_cave() -> None:
    assert TYPE_CLASSES["LOOKOUT_TOWER"] == "Q1440300"
    assert TYPE_CLASSES["ZOO"] == "Q43501"
    assert TYPE_CLASSES["CAVE"] == "Q35509"


def test_build_query_includes_class_and_mapped_properties() -> None:
    query = build_query("Q23413")
    assert "wd:Q23413" in query
    assert "wd:Q213" in query
    assert "wdt:P18" in query
    assert "wdt:P4075" in query
    assert "wdt:P625" in query
    assert "wdt:P856" in query
    assert "wdt:P4856" in query
    assert "?item wdt:P131+ ?obec" in query
    assert "cs.wikipedia.org" in query
    with pytest.raises(ValueError):
        build_query("not-a-qid")


def test_parse_wkt_point() -> None:
    assert parse_wkt_point("Point(16.891111 49.704167)") == (49.704167, 16.891111)
    lat, lon = parse_wkt_point("<http://www.opengis.net/def/crs/EPSG/0/4326> Point(14.18806 49.93944)")
    assert lat == 49.93944
    assert lon == 14.18806
    assert parse_wkt_point(None) == (None, None)
    assert parse_wkt_point("not a point") == (None, None)


def test_parse_sparql_json_from_fixture() -> None:
    records = _sample_records()
    by_qid = _by_qid(records)
    assert set(by_qid) == {
        "Q122922",
        "Q214651",
        "Q1010040",
        "Q999000001",
        "Q999000002",
        "Q999000003",
    }
    assert count_without_gps(records) == 1

    bouzov = by_qid["Q122922"]
    assert bouzov.source_type == "wikidata"
    assert bouzov.name == "Bouzov"
    assert bouzov.types == ["CASTLE"]
    assert bouzov.latitude == pytest.approx(49.704167)
    assert bouzov.longitude == pytest.approx(16.891111)
    assert bouzov.municipality == "Bouzov"
    assert bouzov.district == "Olomouc"
    assert bouzov.region == "Olomoucký kraj"
    assert bouzov.official_website == "https://www.hrad-bouzov.cz/"
    assert bouzov.wikipedia_url == "https://cs.wikipedia.org/wiki/Bouzov_(hrad)"
    assert bouzov.external_ids["wikidata"] == "Q122922"
    assert bouzov.external_ids["uskp"] == "19895/8-2468"
    assert bouzov.external_ids["wikipedia"] == "cs:Bouzov_(hrad)"
    assert bouzov.license == "CC0"
    assert bouzov.source_url == "https://www.wikidata.org/wiki/Q122922"
    assert bouzov.image is not None
    assert "Hrad_Bouzov.jpg" in bouzov.image["original_url"]
    assert bouzov.image["thumbnail_url"].endswith("width=640")
    assert bouzov.image["source"] == "wikimedia_commons"

    becov = by_qid["Q1010040"]
    assert set(becov.types) == {"CASTLE", "CHATEAU"}

    missing_gps = by_qid["Q999000001"]
    assert missing_gps.latitude is None
    assert missing_gps.longitude is None
    assert missing_gps.types == ["CASTLE"]

    testhrad = by_qid["Q999000002"]
    assert testhrad.types == ["RUIN"]
    assert testhrad.visitability == "FREE_ACCESS"

    tvrz = by_qid["Q999000003"]
    assert tvrz.types == ["MANOR"]
    assert tvrz.external_ids["uskp"] == "12345/1-0000"


def test_invalid_sparql_json_raises() -> None:
    with pytest.raises(ValueError, match="results.bindings"):
        parse_sparql_response({"head": {}}, fetched_at="t")


def test_qid_from_uri() -> None:
    assert qid_from_uri("http://www.wikidata.org/entity/Q122922") == "Q122922"
    assert qid_from_uri("not-qid") is None


def test_image_from_p18() -> None:
    image = image_from_p18("http://commons.wikimedia.org/wiki/Special:FilePath/Hrad%20Bouzov.jpg")
    assert image is not None
    assert image["thumbnail_url"].endswith("?width=640")
    assert "File:Hrad_Bouzov.jpg" in image["original_url"]


def test_qid_saved_as_place_source(session: Session) -> None:
    records = _sample_records()
    result = apply_import(session, records, "wikidata", make_backup=True)
    assert result.records_created == 6
    assert result.counts_ok()

    sources = list(session.scalars(select(PlaceSource).where(PlaceSource.source_type == "wikidata")).all())
    qids = {row.external_id for row in sources}
    assert qids == {item.external_id for item in records}
    assert all(row.external_id and row.external_id.startswith("Q") for row in sources)

    bouzov = session.scalar(select(Place).where(Place.name == "Bouzov"))
    assert bouzov is not None
    testhrad = session.scalar(select(Place).where(Place.name == "Zřícenina Testhrad"))
    assert testhrad is not None
    assert testhrad.visitability == "FREE_ACCESS"
    uskp = session.scalar(
        select(PlaceSource).where(PlaceSource.source_type == "uskp", PlaceSource.external_id == "19895/8-2468")
    )
    assert uskp is not None
    assert uskp.place_id == bouzov.id
    assert uskp.source_url == "https://pamatkovykatalog.cz/uskp/19895%2F8-2468"
    wiki = session.scalar(
        select(PlaceSource).where(PlaceSource.source_type == "wikipedia", PlaceSource.external_id == "cs:Bouzov_(hrad)")
    )
    assert wiki is not None
    assert wiki.source_url == "https://cs.wikipedia.org/wiki/Bouzov_(hrad)"
    photo = session.scalar(select(PlacePhoto).where(PlacePhoto.place_id == bouzov.id))
    assert photo is not None
    assert photo.source == "wikimedia_commons"


def test_second_run_zero_created_same_public_id(session: Session) -> None:
    records = _sample_records()
    first = apply_import(session, records, "wikidata", make_backup=True, extra_log=fetch_summary(records))
    assert first.records_created == 6
    ids = {row.public_id for row in session.scalars(select(Place)).all()}
    assert len(ids) == 6
    assert "without_gps=1" in first.log

    second = apply_import(session, records, "wikidata", make_backup=True)
    assert second.records_created == 0
    assert second.records_updated + second.records_unchanged == 6
    assert second.counts_ok()
    again = {row.public_id for row in session.scalars(select(Place)).all()}
    assert again == ids
    qids = [
        row.external_id
        for row in session.scalars(select(PlaceSource).where(PlaceSource.source_type == "wikidata")).all()
    ]
    assert len(qids) == len(set(qids)) == 6


def test_place_without_gps_is_imported_needs_review(session: Session) -> None:
    records = _sample_records()
    apply_import(session, records, "wikidata", make_backup=True)
    missing = session.scalar(select(Place).where(Place.name == "Hrad Bezsouřadnic"))
    assert missing is not None
    assert missing.latitude is None
    assert missing.longitude is None
    assert missing.quality_status == "NEEDS_REVIEW"
    with_gps = session.scalar(select(Place).where(Place.name == "Bouzov"))
    assert with_gps is not None
    assert with_gps.quality_status == "PROBABLE"


def test_second_qid_attaches_does_not_overwrite(session: Session) -> None:
    records = _sample_records()
    apply_import(session, records, "wikidata", make_backup=True)
    bouzov = session.scalar(select(Place).where(Place.name == "Bouzov"))
    assert bouzov is not None
    public_id = bouzov.public_id

    incoming = CanonicalRecord.from_dict(
        {
            "source_type": "wikidata",
            "external_id": "Q888000001",
            "external_ids": {"wikidata": "Q888000001", "uskp": "19895/8-2468"},
            "name": "Bouzov",
            "types": ["CASTLE"],
            "latitude": 49.704167,
            "longitude": 16.891111,
            "municipality": "Bouzov",
            "district": "Olomouc",
            "fetched_at": "2026-08-14T22:00:00+02:00",
        }
    )
    result = apply_import(session, [incoming], "wikidata", make_backup=True)
    assert result.records_created == 0
    session.refresh(bouzov)
    assert bouzov.public_id == public_id
    qids = {
        row.external_id
        for row in session.scalars(
            select(PlaceSource).where(PlaceSource.place_id == bouzov.id, PlaceSource.source_type == "wikidata")
        ).all()
    }
    assert qids == {"Q122922", "Q888000001"}
    still = session.scalar(
        select(PlaceSource).where(PlaceSource.source_type == "wikidata", PlaceSource.external_id == "Q122922")
    )
    assert still is not None
    assert still.place_id == bouzov.id
    assert session.scalar(select(func.count()).select_from(Place)) == 6


def test_client_user_agent_timeout_and_split_by_type() -> None:
    payload = load_bundle_file(SAMPLE_SPARQL_FIXTURE)
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["User-Agent"] == USER_AGENT
        assert str(request.url).startswith(ENDPOINT)
        assert request.method == "POST"
        body = unquote_plus(request.content.decode())
        matched = None
        for type_code, class_qid in TYPE_CLASSES.items():
            if f"wd:{class_qid}" in body and "wdt:P31" in body:
                matched = type_code
                break
        assert matched is not None
        seen.append(matched)
        return httpx.Response(200, json=payload[matched])

    client = WikidataClient(transport=httpx.MockTransport(handler), sleep=lambda _s: None)
    bundle_out = client.fetch_bundle()
    assert seen == list(TYPE_CLASSES)
    records = records_from_bundle(bundle_out, "2026-08-14T21:00:00+02:00")
    assert len(records) == 6


def test_client_retries_timeout_then_succeeds() -> None:
    payload = load_bundle_file(SAMPLE_SPARQL_FIXTURE)
    calls = {"n": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] < 3:
            raise httpx.ReadTimeout("slow", request=request)
        return httpx.Response(200, json=payload["CASTLE"])

    client = WikidataClient(transport=httpx.MockTransport(handler), sleep=lambda _s: None)
    data = client.fetch_class("Q23413")
    assert calls["n"] == 3
    assert "results" in data


def test_client_gives_up_after_retries() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("still slow", request=request)

    client = WikidataClient(transport=httpx.MockTransport(handler), sleep=lambda _s: None, max_retries=2)
    with pytest.raises(SparqlError, match="Q23413"):
        client.fetch_class("Q23413")


def test_settlement_part_walks_to_municipality_and_composes_address() -> None:
    payload = {
        "head": {"vars": ["item", "itemLabel", "coord", "obecLabel", "okresLabel", "krajLabel", "castLabel", "cp"]},
        "results": {
            "bindings": [
                {
                    "item": {"type": "uri", "value": "http://www.wikidata.org/entity/Q10712273"},
                    "itemLabel": {"xml:lang": "cs", "type": "literal", "value": "Adršpach"},
                    "coord": {
                        "datatype": "http://www.opengis.net/ont/geosparql#wktLiteral",
                        "type": "literal",
                        "value": "Point(16.1109 50.6189)",
                    },
                    "obecLabel": {"xml:lang": "cs", "type": "literal", "value": "Adršpach"},
                    "okresLabel": {"xml:lang": "cs", "type": "literal", "value": "okres Náchod"},
                    "krajLabel": {"xml:lang": "cs", "type": "literal", "value": "Královéhradecký kraj"},
                    "castLabel": {"xml:lang": "cs", "type": "literal", "value": "Dolní Adršpach"},
                    "cp": {"type": "literal", "value": "75"},
                }
            ]
        },
    }
    records = parse_sparql_response(payload, extra_type="CHATEAU", fetched_at="t")
    assert len(records) == 1
    place = records[0]
    assert place.municipality == "Adršpach"
    assert place.district == "Náchod"
    assert place.region == "Královéhradecký kraj"
    assert place.address == "Dolní Adršpach 75"
    assert place.latitude == pytest.approx(50.6189)
    assert place.longitude == pytest.approx(16.1109)
    assert compose_address("12", "Bouzov", "Bouzov") == "Bouzov 12"


def test_records_from_single_sparql_response() -> None:
    castle = load_bundle_file(SAMPLE_SPARQL_FIXTURE)["CASTLE"]
    records = parse_sparql_response(castle, extra_type="CASTLE", fetched_at="t")
    assert {item.external_id for item in records} == {"Q122922", "Q214651", "Q1010040", "Q999000001"}
