"""Otisky podle typu a vosk podle kraje — data z shared/stamp-art.json."""

from __future__ import annotations

import json
from functools import lru_cache
from html import escape
from typing import Any

from markupsafe import Markup

from app.config import REPO_ROOT
from app.db.models import Place
from app.services.czech_regions import match_czech_region


def _art_path():
    return REPO_ROOT / "shared" / "stamp-art.json"


@lru_cache(maxsize=1)
def _load_art() -> dict[str, Any]:
    return json.loads(_art_path().read_text(encoding="utf-8"))


_ART = _load_art()
TYPE_PRIORITY: tuple[str, ...] = tuple(_ART["type_priority"])
KIND_BY_TYPE: dict[str, str] = dict(_ART["kind_by_type"])
REGION_WAX: dict[str, str] = dict(_ART["region_wax"])
DEFAULT_WAX: str = str(_ART["default_wax"])
WANT_WAX: str = str(_ART["want_wax"])
STAMP_PATHS: dict[str, str] = dict(_ART["stamp_paths"])


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
