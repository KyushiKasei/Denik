from __future__ import annotations

from app.services.visit_worth import is_weak_stub, is_worth_visiting, parse_worth_param, visit_score


def test_ruin_with_free_access_is_worth_visiting() -> None:
    assert is_worth_visiting(
        condition="RUIN",
        visitability="FREE_ACCESS",
        has_image=True,
    )


def test_extinct_and_remains_are_chaff() -> None:
    assert not is_worth_visiting(condition="EXTINCT", visitability="EXTINCT")
    assert not is_worth_visiting(condition="REMAINS", visitability="FREE_ACCESS")


def test_nkp_without_photo_still_counts() -> None:
    assert is_worth_visiting(condition="UNKNOWN", visitability="UNKNOWN", heritage_status="NKP")
    assert not is_weak_stub(condition="UNKNOWN", visitability="UNKNOWN", heritage_status="NKP")


def test_private_and_weak_stub_are_hidden() -> None:
    assert not is_worth_visiting(condition="PRESERVED", visitability="PRIVATE")
    assert is_weak_stub(condition="UNKNOWN", visitability="UNKNOWN")
    assert not is_worth_visiting(condition="UNKNOWN", visitability="UNKNOWN")


def test_visit_score_prefers_preserved_nkp() -> None:
    castle = visit_score(
        condition="PRESERVED",
        visitability="REGULAR",
        heritage_status="NKP",
        official_website="https://example.test",
        wikipedia_url="https://cs.wikipedia.org/wiki/X",
    )
    ruin = visit_score(condition="RUIN", visitability="FREE_ACCESS")
    assert castle > ruin


def test_parse_worth_param() -> None:
    assert parse_worth_param(None) is None
    assert parse_worth_param("all") is False
    assert parse_worth_param("ALL") is False
    assert parse_worth_param("0") is False
    assert parse_worth_param("false") is False
    assert parse_worth_param("visit") is True
    assert parse_worth_param("1") is True
    assert parse_worth_param("true") is True
    assert parse_worth_param("nope") is None
