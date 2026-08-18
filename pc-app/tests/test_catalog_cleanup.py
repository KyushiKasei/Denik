from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import Place, PlaceFieldOverride, PlaceSource
from app.services.catalog_cleanup import (
    BARRANDOV_ID,
    CLEANUP_NOTE,
    KARLSTEJN_CASTLE_ID,
    TEXTILKA_ID,
    UHERCICE_ID,
    UNCLEAR_KARLSTEIN_QID,
    VYSEHRAD_ID,
    cleanup_catalog,
)
from app.services.display import display_place_name
from app.services.overrides import apply_value_to_place, upsert_override
from app.services.places import PlaceFilters, dashboard_stats, list_places
from app.services.ruins import is_ruin, ruin_union_count


def _place(session: Session, name: str, types: list[str], **kwargs) -> Place:
    public_id = kwargs.pop("public_id", None)
    sources = kwargs.pop("sources", [])
    place = Place(name=name, **kwargs)
    if public_id:
        place.public_id = public_id
    session.add(place)
    session.flush()
    apply_value_to_place(place, "types", types, session)
    for source_type, external_id in sources:
        session.add(PlaceSource(place_id=place.id, source_type=source_type, external_id=external_id))
    session.commit()
    session.refresh(place)
    return place


def test_is_ruin_type_or_condition(session: Session) -> None:
    by_type = _place(session, "typ", ["RUIN"], condition="UNKNOWN")
    by_cond = _place(session, "stav", ["CASTLE"], condition="RUIN")
    both = _place(session, "oboje", ["RUIN"], condition="RUIN")
    castle = _place(session, "hrad", ["CASTLE"], condition="PRESERVED")
    extinct = _place(session, "zanik", ["RUIN"], condition="EXTINCT")
    assert is_ruin(by_type)
    assert is_ruin(by_cond)
    assert is_ruin(both)
    assert not is_ruin(castle)
    assert is_ruin(extinct)
    assert ruin_union_count(session) == 4


def test_backfill_unknown_ruin_condition_skips_override(session: Session) -> None:
    target = _place(session, "zřícenina", ["RUIN"], condition="UNKNOWN", visitability="UNKNOWN")
    preserved = _place(session, "hrad", ["RUIN"], condition="PRESERVED")
    locked = _place(session, "zámek", ["RUIN"], condition="UNKNOWN")
    upsert_override(session, locked, "condition", "UNKNOWN", note="ručně")
    session.commit()

    dry = cleanup_catalog(session, dry_run=True)
    session.refresh(target)
    assert dry.condition_backfill == 1
    assert dry.skipped_override == 1
    assert target.condition == "UNKNOWN"

    result = cleanup_catalog(session, dry_run=False)
    session.refresh(target)
    session.refresh(preserved)
    session.refresh(locked)
    assert result.condition_backfill == 1
    assert result.skipped_override == 1
    assert target.condition == "RUIN"
    assert preserved.condition == "PRESERVED"
    assert locked.condition == "UNKNOWN"
    assert target.visitability == "FREE_ACCESS"


def test_curated_fixes_and_detach_source(session: Session) -> None:
    karl = _place(
        session,
        "Karlštejn",
        ["CASTLE"],
        public_id=KARLSTEJN_CASTLE_ID,
        condition="PRESERVED",
        visitability="REGULAR",
        short_description="Nejasný záznam blízko Karlštejna pro review.",
        sources=[("wikidata", "Q214651"), ("wikidata", UNCLEAR_KARLSTEIN_QID)],
    )
    vysehrad = _place(
        session,
        "Vyšehrad",
        ["CASTLE", "RUIN"],
        public_id=VYSEHRAD_ID,
        condition="RUIN",
        visitability="REGULAR",
    )
    _place(session, "Barrandovské terasy", ["LOOKOUT_TOWER"], public_id=BARRANDOV_ID)
    _place(session, "Administrativní budova textilky", ["PALACE"], public_id=TEXTILKA_ID)
    _place(
        session,
        "zámek Uherčice",
        ["CHATEAU"],
        public_id=UHERCICE_ID,
        municipality="Brno; Milotice; Uherčice",
        district="Brno-město; Hodonín; Znojmo",
        quality_status="NEEDS_REVIEW",
    )

    result = cleanup_catalog(session, dry_run=False)
    assert result.curated == 5
    assert result.detached_sources == 1
    assert result.missing == []

    session.refresh(karl)
    session.refresh(vysehrad)
    assert karl.short_description is None
    assert not any(item.external_id == UNCLEAR_KARLSTEIN_QID for item in karl.sources)
    assert [item.code for item in vysehrad.types] == ["CASTLE"]
    assert vysehrad.condition == "PRESERVED"
    override = session.get(PlaceFieldOverride, (vysehrad.id, "condition"))
    assert override is not None
    assert override.note == CLEANUP_NOTE

    barr = session.scalar(select_place(BARRANDOV_ID, session))
    textilka = session.scalar(select_place(TEXTILKA_ID, session))
    uher = session.scalar(select_place(UHERCICE_ID, session))
    assert [item.code for item in barr.types] == ["OTHER"]
    assert [item.code for item in textilka.types] == ["OTHER"]
    assert uher.municipality == "Uherčice"
    assert uher.district == "Znojmo"

    again = cleanup_catalog(session, dry_run=False)
    assert again.condition_backfill == 0
    assert again.curated == 0
    assert again.already == 5


def select_place(public_id: str, session: Session):
    from sqlalchemy import select

    return select(Place).where(Place.public_id == public_id)


def test_pc_ruin_union_filter_matches_dashboard(session: Session) -> None:
    _place(session, "typ", ["RUIN"], condition="UNKNOWN")
    _place(session, "stav", ["CASTLE"], condition="RUIN")
    stats = dashboard_stats(session)
    assert stats.ruin_union == 2
    found = list_places(session, PlaceFilters(ruin_union=True, worth=False))
    assert {place.name for place in found.places} == {"typ", "stav"}


def test_display_place_name_capitalizes_first_letter() -> None:
    assert display_place_name("zámek Kroměříž") == "Zámek Kroměříž"
    assert display_place_name("Karlštejn") == "Karlštejn"
    assert display_place_name("") == ""
