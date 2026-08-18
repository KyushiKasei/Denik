from __future__ import annotations

from types import SimpleNamespace

from app.services.source_urls import identity_source_url, is_http_url, photo_display_url, source_page_url


def test_identity_urls() -> None:
    assert identity_source_url("wikidata", "Q106782997") == "https://www.wikidata.org/wiki/Q106782997"
    assert identity_source_url("wikipedia", "cs:Dolní_hrádek") == "https://cs.wikipedia.org/wiki/Doln%C3%AD_hr%C3%A1dek"
    assert identity_source_url("uskp", "1000128207_0001") == "https://pamatkovykatalog.cz/uskp/1000128207_0001"
    assert identity_source_url("uskp", "19895/8-2468") == "https://pamatkovykatalog.cz/uskp/19895%2F8-2468"
    assert identity_source_url("osm", "way/123") == "https://www.openstreetmap.org/way/123"
    assert identity_source_url("wikipedia", "broken") is None
    assert identity_source_url("unknown", "x") is None


def test_source_page_url_prefers_identity_over_stored_wikidata() -> None:
    source = SimpleNamespace(
        source_type="wikipedia",
        external_id="cs:Dolní_hrádek",
        source_url="https://www.wikidata.org/wiki/Q106782997",
    )
    assert source_page_url(source) == "https://cs.wikipedia.org/wiki/Doln%C3%AD_hr%C3%A1dek"


def test_is_http_url() -> None:
    assert is_http_url("https://cs.wikipedia.org/wiki/X")
    assert not is_http_url("['MANOR']")
    assert not is_http_url(None)


def test_photo_display_url_prefers_thumbnail() -> None:
    photo = SimpleNamespace(
        thumbnail_url="https://commons.wikimedia.org/wiki/Special:FilePath/X.jpg?width=640",
        original_url="https://commons.wikimedia.org/wiki/File:X.jpg",
        source_url="https://commons.wikimedia.org/wiki/File:X.jpg",
    )
    assert photo_display_url(photo) == photo.thumbnail_url
    assert photo_display_url(None) is None
    missing = SimpleNamespace(thumbnail_url=None, original_url=None, source_url="javascript:alert(1)")
    assert photo_display_url(missing) is None
