"""České UNESCO objekty, které v katalogu existují jako hrad / zámek / salet.

Oficiální zápisy WHC jsou často krajina nebo historické jádro. Sem patří jen
návštěvní objekty v našich typech. Příznak se drží override, aby ho import nesmazal.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Place, PlaceSource, now_iso
from app.services.backup import backup_before_import
from app.services.matching import normalize_label
from app.services.merge_places import merge_places
from app.services.overrides import has_override, upsert_override

UNESCO_OVERRIDE_NOTE = "UNESCO světové dědictví — doplněno podle oficiálního seznamu WHC"


@dataclass(frozen=True)
class UnescoSite:
    key: str
    wikidata: frozenset[str] = field(default_factory=frozenset)
    uskp: frozenset[str] = field(default_factory=frozenset)
    catalog: frozenset[str] = field(default_factory=frozenset)
    names: frozenset[tuple[str, str]] = field(default_factory=frozenset)


def _site(
    key: str,
    *,
    wikidata: tuple[str, ...] = (),
    uskp: tuple[str, ...] = (),
    catalog: tuple[str, ...] = (),
    names: tuple[tuple[str, str], ...] = (),
) -> UnescoSite:
    return UnescoSite(
        key=key,
        wikidata=frozenset(wikidata),
        uskp=frozenset(uskp),
        catalog=frozenset(catalog),
        names=frozenset((normalize_label(name), normalize_label(municipality)) for name, municipality in names),
    )


# Jedna položka = jeden návštěvní objekt. Duplicity (katalog vs Wikidata) se sloučí.
UNESCO_SITES: tuple[UnescoSite, ...] = (
    _site("prazsky-hrad", wikidata=("Q193369",), uskp=("1000151651",)),
    _site("vysehrad", wikidata=("Q616334",), uskp=("1000001769",)),
    _site(
        "pruhonice",
        wikidata=("Q10968666",),
        uskp=("1000145390", "365"),
        catalog=("1000145390",),
    ),
    _site("cesky-krumlov", wikidata=("Q2164919",), uskp=("1000125170",)),
    _site("telc", wikidata=("Q12058592",), names=(("Telč", "Telč"),)),
    _site(
        "litomysl",
        wikidata=("Q2164885",),
        uskp=("1000147510",),
        catalog=("1000147510",),
    ),
    _site(
        "kromeriz",
        wikidata=("Q200693",),
        uskp=("1000127688", "219"),
        catalog=("1000127688", "2000012761"),
        names=(("zámek Kroměříž", "Kroměříž"), ("Arcibiskupský zámek", "Kroměříž")),
    ),
    _site("lednice", wikidata=("Q370990",), uskp=("1000159057",)),
    _site("valtice", wikidata=("Q877062",), uskp=("1000140198",)),
    _site("januv-hrad", wikidata=("Q613416",), uskp=("1000147970",)),
    _site("kladruby", wikidata=("Q133824306",), uskp=("1000126748_0001",)),
    _site("minaret-lednice", wikidata=("Q1228860",), uskp=("1000159057_0537",)),
    _site("dianin-chram", wikidata=("Q1208929",), uskp=("1000146101",)),
    _site(
        "belveder-valtice",
        wikidata=("Q11068580", "Q735278"),
        uskp=("2000011704_0001", "25475/7-1757"),
        catalog=("2000011704_0001",),
    ),
    _site(
        "rybnicni-zamecek",
        wikidata=("Q12050412",),
        uskp=("1198705589", "87452/7-1347"),
        catalog=("1198705589",),
    ),
    _site("lovecky-zamecek", wikidata=("Q12034053",), uskp=("1316962874",)),
    _site(
        "katzelsdorf",
        wikidata=("Q1678356",),
        uskp=("2000008132_0001", "106708"),
        catalog=("2000008132_0001",),
    ),
    _site("lednice-jizdarna", wikidata=("Q80097338",)),
    _site(
        "hranicni-zamecek",
        catalog=("2000019582",),
        uskp=("36467/7-1245",),
        names=(("Hraniční zámeček", "Hlohovec"),),
    ),
    _site("tri-gracie", wikidata=("Q12060369",), uskp=("1000130808",)),
    _site(
        "pohansko",
        wikidata=("Q12046033",),
        uskp=("1000130433", "19654/7-1160"),
        catalog=("1000130433",),
    ),
    _site(
        "vlassky-dvur",
        wikidata=("Q1087662",),
        uskp=("1000126491", "119"),
        catalog=("1000126491",),
    ),
    _site("hradek-kutna-hora", wikidata=("Q11710201",), uskp=("1000140783",)),
)


@dataclass
class UnescoSyncResult:
    merged: int = 0
    flagged: int = 0
    already: int = 0
    missing: list[str] = field(default_factory=list)
    backup_path: Path | None = None


def site_matches_place(site: UnescoSite, place: Place) -> bool:
    for source in place.sources:
        ext = (source.external_id or "").strip()
        if not ext:
            continue
        if source.source_type == "wikidata" and ext in site.wikidata:
            return True
        if source.source_type == "uskp" and ext in site.uskp:
            return True
        if source.source_type == "pamatkovy_katalog" and ext in site.catalog:
            return True
    name_key = (normalize_label(place.name), normalize_label(place.municipality))
    return name_key in site.names


def find_site_places(session: Session, site: UnescoSite) -> list[Place]:
    ids: set[int] = set()
    for source_type, values in (
        ("wikidata", site.wikidata),
        ("uskp", site.uskp),
        ("pamatkovy_katalog", site.catalog),
    ):
        if not values:
            continue
        ids.update(
            session.scalars(
                select(PlaceSource.place_id).where(
                    PlaceSource.source_type == source_type,
                    PlaceSource.external_id.in_(values),
                )
            ).all()
        )
    if site.names:
        for pid, name, municipality in session.execute(
            select(Place.id, Place.name, Place.municipality).where(Place.archived_at.is_(None))
        ):
            if (normalize_label(name), normalize_label(municipality)) in site.names:
                ids.add(pid)
    if not ids:
        return []
    return list(
        session.scalars(select(Place).where(Place.id.in_(ids), Place.archived_at.is_(None))).all()
    )


def _winner_score(place: Place) -> tuple[int, int, int, int, int]:
    has_gps = 1 if place.latitude is not None and place.longitude is not None else 0
    has_wiki = 1 if any(item.source_type == "wikidata" and item.external_id for item in place.sources) else 0
    vis = 0 if (place.visitability or "UNKNOWN") == "UNKNOWN" else 1
    nkp = 1 if place.heritage_status == "NKP" else 0
    return (has_gps, has_wiki, vis, nkp, -place.id)


def pick_winner(places: list[Place]) -> Place:
    if not places:
        raise ValueError("Žádné místo k výběru vítěze.")
    return max(places, key=_winner_score)


def _flag_place(session: Session, place: Place) -> bool:
    """Vrátí True, pokud se příznak nově zapnul."""
    changed = not bool(place.unesco)
    if changed:
        place.unesco = 1
        place.updated_at = now_iso()
    if not has_override(session, place.id, "unesco"):
        upsert_override(session, place, "unesco", 1, note=UNESCO_OVERRIDE_NOTE)
    return changed


def sync_unesco_places(session: Session, *, make_backup: bool = False) -> UnescoSyncResult:
    result = UnescoSyncResult()
    session.commit()
    if make_backup:
        result.backup_path = backup_before_import(session, "unesco")
        session.expire_all()

    winners: list[tuple[Place, bool]] = []
    for site in UNESCO_SITES:
        matches = find_site_places(session, site)
        if not matches:
            result.missing.append(site.key)
            continue
        winner = pick_winner(matches)
        had_flag = bool(winner.unesco)
        for loser in [item for item in matches if item.id != winner.id]:
            merge_places(session, winner, loser)
            result.merged += 1
            session.refresh(winner)
        winners.append((winner, had_flag))

    flagged_ids: set[int] = set()
    for winner, had_flag in winners:
        session.refresh(winner)
        if winner.id in flagged_ids:
            continue
        newly = _flag_place(session, winner)
        if newly or not had_flag:
            result.flagged += 1
        else:
            result.already += 1
        flagged_ids.add(winner.id)

    session.commit()
    return result
