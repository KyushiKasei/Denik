"""Otisky podle typu a vosk podle kraje — stejné siluety jako PWA."""

from __future__ import annotations

from html import escape

from markupsafe import Markup

from app.db.models import Place
from app.services.czech_regions import match_czech_region

TYPE_PRIORITY = (
    "RUIN",
    "CASTLE",
    "CHATEAU",
    "FORTRESS",
    "MANOR",
    "PALACE",
    "LOOKOUT_TOWER",
    "ZOO",
    "CAVE",
    "OTHER",
)

KIND_BY_TYPE = {
    "RUIN": "ruin",
    "CASTLE": "castle",
    "CHATEAU": "chateau",
    "FORTRESS": "fortress",
    "MANOR": "manor",
    "PALACE": "palace",
    "LOOKOUT_TOWER": "tower",
    "ZOO": "zoo",
    "CAVE": "cave",
    "OTHER": "other",
}

REGION_WAX = {
    "KVK": "#8a3d2c",
    "ULK": "#3d5a40",
    "LBK": "#2f5f73",
    "PLK": "#6b4a2e",
    "STC": "#4a5c38",
    "PHA": "#8b2e2e",
    "JHC": "#3d4f7a",
    "HKK": "#6a3d5c",
    "PAK": "#5a6b2e",
    "VYS": "#7a5a28",
    "OLK": "#2e5a4a",
    "MSK": "#5a3d2e",
    "ZLK": "#4a3d6b",
    "JHM": "#7a3d4a",
}

DEFAULT_WAX = "#3d5a40"
WANT_WAX = "#c9a227"

STAMP_PATHS = {
    "castle": "M8 52h48V28l-8-8h-8v-8h-8v8h-8V12h-8v8H16l-8 8z M20 52V36h8v16h8V36h8v16",
    "chateau": "M6 50h52V30L32 12 6 30z M16 50V36h10v14h12V36h10v14",
    "ruin": "M8 52h48V34l-10-14h-8v10l-8-12h-10v16H8z M28 52V40h8v12",
    "fortress": "M32 10 54 28v24H10V28z M22 52V36h20v16",
    "manor": "M8 50h48V32L32 14 8 32z M24 50V38h16v12",
    "palace": "M4 50h56V28H4z M10 28V16h8v12h8V16h8v12h8V16h8v12",
    "tower": "M26 54h12V22l-6-12-6 12z M22 54h20",
    "zoo": "M18 44c0-10 28-10 28 0v8H18z M24 28c0-6 16-6 16 0",
    "cave": "M8 52c0-20 16-36 24-36s24 16 24 36z M20 52c4-12 20-12 24 0",
    "other": "M32 12 52 32 32 52 12 32z",
}


def stamp_kind_from_types(codes: list[str]) -> str:
    for code in TYPE_PRIORITY:
        if code in codes and code in KIND_BY_TYPE:
            return KIND_BY_TYPE[code]
    return "other"


def wax_color_for_region(raw: str | None) -> str:
    region = match_czech_region(raw)
    if region is None:
        return DEFAULT_WAX
    return REGION_WAX.get(region.id, DEFAULT_WAX)


def stamp_art_for_place(place: Place | None) -> tuple[str, str]:
    if place is None:
        return "other", DEFAULT_WAX
    kind = stamp_kind_from_types([item.code for item in place.types])
    return kind, wax_color_for_region(place.region)


def stamp_svg(kind: str, wax: str, *, size: int = 64, empty: bool = False) -> Markup:
    path = STAMP_PATHS.get(kind, STAMP_PATHS["other"])
    color = "#9a9084" if empty else escape(wax, quote=True)
    dash = ' stroke-dasharray="4 4"' if empty else ""
    return Markup(
        f'<svg class="stamp-mark{" is-empty" if empty else ""}" viewBox="0 0 64 64" '
        f'width="{size}" height="{size}" aria-hidden="true">'
        f'<circle cx="32" cy="32" r="30" fill="none" stroke="{color}" stroke-width="2"{dash}/>'
        f'<path d="{path}" fill="none" stroke="{color}" stroke-width="2.4" '
        f'stroke-linejoin="round" stroke-linecap="round"/></svg>'
    )


def visit_stamp_svg(visit, *, size: int = 40) -> Markup:
    kind, wax = stamp_art_for_place(getattr(visit, "place", None))
    return stamp_svg(kind, wax, size=size)


def place_stamp_svg(place, *, size: int = 48) -> Markup:
    kind, wax = stamp_art_for_place(place)
    return stamp_svg(kind, wax, size=size)
