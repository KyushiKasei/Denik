from app.services.display import (
    explain_match_reason,
    format_distance_m,
    incoming_is_sparse,
    incoming_review_label,
)


def test_explain_match_reason_c1_c2() -> None:
    assert "Blízko na mapě (198\u00a0m)" in explain_match_reason("C1 distance=198.3m similarity=0.762")
    assert "76\u00a0%" in explain_match_reason("C1 distance=198.3m similarity=0.762")
    assert "Nestačí to k automatickému sloučení" in explain_match_reason(
        "C1 distance=198.3m similarity=0.762"
    )
    c2 = explain_match_reason("C2 same_municipality similarity=0.851")
    assert "stejné obci" in c2
    assert "85\u00a0%" in c2
    both = explain_match_reason(
        "C1 distance=43.5m similarity=0.863; C2 same_municipality similarity=0.863"
    )
    assert "Blízko na mapě (44\u00a0m)" in both
    assert "stejné obci" in both


def test_explain_match_reason_malformed_numbers() -> None:
    text = explain_match_reason("C1 distance=1.2.3m similarity=nope")
    assert "Blízko na mapě" in text
    assert "Nestačí to k automatickému sloučení" in text


def test_explain_match_reason_multiple_candidates() -> None:
    text = explain_match_reason("C2 same_municipality similarity=1.000", 3)
    assert "názvy jsou stejné" in text
    assert "3 podobná místa" in text


def test_explain_match_reason_a_and_b() -> None:
    assert "více místům" in explain_match_reason("A: stejné ID nebo stejná fotka na více různých Place — neslučovat")
    assert "fotka" in explain_match_reason("A: stejné ID nebo stejná fotka na více různých Place — neslučovat")
    assert "víc míst" in explain_match_reason("B: více Place vyhovuje pravděpodobné shodě — neslučovat")


def test_incoming_review_label() -> None:
    assert incoming_review_label('{"name": "Palác ARA", "municipality": "Praha"}') == "Palác ARA (Praha)"
    assert incoming_review_label('{"name": "Telč", "municipality": "Telč"}') == "Telč"
    assert incoming_review_label("not-json") == "—"


def test_format_distance_m() -> None:
    assert format_distance_m(50.0842, 14.4242, 50.0833, 14.4218) == "198\u00a0m"
    assert format_distance_m(None, None, 50.0, 14.0) is None


def test_incoming_is_sparse() -> None:
    assert incoming_is_sparse({"name": "X", "latitude": 50.0, "longitude": 14.0})
    assert not incoming_is_sparse({"wikipedia_url": "https://cs.wikipedia.org/wiki/X"})
    assert not incoming_is_sparse(
        {"image": {"thumbnail_url": "https://commons.wikimedia.org/wiki/Special:FilePath/X.jpg"}}
    )


def test_identity_conflicts_different_wikidata() -> None:
    from types import SimpleNamespace

    from app.services.display import identity_conflicts

    place = SimpleNamespace(
        wikipedia_url="https://cs.wikipedia.org/wiki/Palác_Věžníků_(Thunovská)",
        sources=[SimpleNamespace(source_type="wikidata", external_id="Q12043615")],
    )
    record = {
        "external_ids": {"wikidata": "Q18340195", "wikipedia": "cs:Palác_Věžníků_(Hybernská)"},
        "wikipedia_url": "https://cs.wikipedia.org/wiki/Palác_Věžníků_(Hybernská)",
    }
    conflicts = identity_conflicts(record, place)
    assert any("Wikidata" in item for item in conflicts)
    assert any("Wikipedii" in item for item in conflicts)
