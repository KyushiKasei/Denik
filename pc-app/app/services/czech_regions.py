"""Schematická mapa 14 krajů — data z shared/czech-regions.json."""

from __future__ import annotations

import json
import unicodedata
from dataclasses import dataclass
from functools import lru_cache

from app.config import REPO_ROOT


@dataclass(frozen=True)
class CzechRegion:
    id: str
    name: str
    short: str
    path: str


def _regions_path():
    return REPO_ROOT / "shared" / "czech-regions.json"


@lru_cache(maxsize=1)
def _load_regions() -> tuple[CzechRegion, ...]:
    payload = json.loads(_regions_path().read_text(encoding="utf-8"))
    return tuple(CzechRegion(**item) for item in payload["regions"])


CZECH_REGIONS: tuple[CzechRegion, ...] = _load_regions()


def fold(value: str) -> str:
    nfd = unicodedata.normalize("NFD", value)
    stripped = "".join(char for char in nfd if unicodedata.category(char) != "Mn")
    return stripped.casefold()


def region_key(value: str) -> str:
    text = fold(value)
    text = text.replace("hlavni mesto", "").replace("kraj", "")
    return " ".join(text.split())


_REGION_BY_KEY: dict[str, CzechRegion] = {}
for _region in CZECH_REGIONS:
    _REGION_BY_KEY[region_key(_region.name)] = _region
    _REGION_BY_KEY[region_key(_region.short)] = _region
    _REGION_BY_KEY[region_key(_region.id)] = _region
_REGION_BY_KEY["praha"] = next(row for row in CZECH_REGIONS if row.id == "PHA")
_REGION_BY_KEY["vysocina"] = next(row for row in CZECH_REGIONS if row.id == "VYS")


def match_czech_region(raw: str | None) -> CzechRegion | None:
    if not raw or not raw.strip():
        return None
    return _REGION_BY_KEY.get(region_key(raw))
