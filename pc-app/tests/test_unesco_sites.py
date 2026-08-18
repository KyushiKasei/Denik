from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Place, PlaceFieldOverride, PlaceSource
from app.services.unesco_sites import (
    UNESCO_OVERRIDE_NOTE,
    UnescoSite,
    pick_winner,
    site_matches_place,
    sync_unesco_places,
)


def _place(session: Session, name: str, **kwargs) -> Place:
    sources = kwargs.pop("sources", [])
    place = Place(
        name=name,
        municipality=kwargs.pop("municipality", None),
        condition=kwargs.pop("condition", "UNKNOWN"),
        visitability=kwargs.pop("visitability", "UNKNOWN"),
        quality_status=kwargs.pop("quality_status", "NEEDS_REVIEW"),
        **kwargs,
    )
    session.add(place)
    session.flush()
    for source_type, external_id in sources:
        session.add(PlaceSource(place_id=place.id, source_type=source_type, external_id=external_id))
    session.commit()
    session.refresh(place)
    return place


def test_site_match_is_exact_uskp_not_prefix() -> None:
    site = UnescoSite(key="lednice", uskp=frozenset({"1000159057"}))
    castle = Place(name="zámek Lednice")
    castle.sources = [PlaceSource(source_type="uskp", external_id="1000159057")]
    minaret = Place(name="Minaret")
    minaret.sources = [PlaceSource(source_type="uskp", external_id="1000159057_0537")]
    assert site_matches_place(site, castle) is True
    assert site_matches_place(site, minaret) is False


def test_pick_winner_prefers_gps_and_wikidata() -> None:
    gps = Place(id=2, name="A", latitude=49.1, longitude=16.2, visitability="REGULAR")
    gps.sources = [PlaceSource(source_type="wikidata", external_id="Q1")]
    catalog = Place(id=9, name="A", heritage_status="NKP", unesco=1, visitability="UNKNOWN")
    catalog.sources = [PlaceSource(source_type="pamatkovy_katalog", external_id="1")]
    assert pick_winner([catalog, gps]) is gps


def test_sync_merges_litomysl_duplicate_and_flags_unesco(session: Session) -> None:
    winner = _place(
        session,
        "zámek Litomyšl",
        municipality="Litomyšl",
        latitude=49.87,
        longitude=16.31,
        visitability="REGULAR",
        quality_status="PROBABLE",
        sources=[("wikidata", "Q2164885"), ("uskp", "1000147510")],
    )
    loser = _place(
        session,
        "zámek Litomyšl",
        municipality="Litomyšl",
        unesco=1,
        heritage_status="NKP",
        sources=[("pamatkovy_katalog", "1000147510"), ("uskp", "9")],
    )
    grotto = _place(
        session,
        "grotta v zámeckém parku v Litomyšli",
        municipality="Litomyšl",
        latitude=49.87,
        longitude=16.31,
        sources=[("uskp", "1000147510_0151"), ("wikidata", "Q64759087")],
    )
    bouzov = _place(
        session,
        "Hrad Bouzov",
        municipality="Bouzov",
        sources=[("wikidata", "Q940492")],
    )

    result = sync_unesco_places(session)
    session.refresh(winner)
    session.refresh(loser)
    session.refresh(grotto)
    session.refresh(bouzov)

    assert result.merged == 1
    assert result.flagged == 1
    assert winner.unesco == 1
    assert winner.heritage_status == "NKP"
    assert loser.archived_at is not None
    assert loser.merged_into_public_id == winner.public_id
    assert grotto.archived_at is None
    assert grotto.unesco == 0
    assert bouzov.unesco == 0
    override = session.get(PlaceFieldOverride, (winner.id, "unesco"))
    assert override is not None
    assert override.note == UNESCO_OVERRIDE_NOTE

    again = sync_unesco_places(session)
    assert again.merged == 0
    assert again.flagged == 0
    assert again.already == 1
    active = list(session.scalars(select(Place).where(Place.archived_at.is_(None), Place.unesco == 1)).all())
    assert [row.public_id for row in active] == [winner.public_id]
