"""Schematická mapa 14 krajů — stejné ID a cesty jako PWA."""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class CzechRegion:
    id: str
    name: str
    short: str
    path: str


CZECH_REGIONS: tuple[CzechRegion, ...] = (
    CzechRegion("KVK", "Karlovarský kraj", "KVK", "M 40,180 L 145,118 205,165 178,262 88,292 38,228 Z"),
    CzechRegion("ULK", "Ústecký kraj", "ULK", "M 145,118 L 285,68 385,92 402,172 278,202 205,165 Z"),
    CzechRegion("LBK", "Liberecký kraj", "LBK", "M 385,92 L 525,52 585,112 522,178 402,172 Z"),
    CzechRegion("PLK", "Plzeňský kraj", "PLK", "M 88,292 L 178,262 252,305 278,425 158,482 68,398 58,322 Z"),
    CzechRegion("STC", "Středočeský kraj", "STČ", "M 205,165 L 402,172 522,178 562,224 582,322 478,382 318,402 252,305 178,262 278,202 Z"),
    CzechRegion("PHA", "Hlavní město Praha", "PHA", "M 412,232 L 462,222 488,252 456,282 408,270 Z"),
    CzechRegion("JHC", "Jihočeský kraj", "JHČ", "M 252,305 L 318,402 478,382 542,452 428,532 248,522 158,482 278,425 Z"),
    CzechRegion("HKK", "Královéhradecký kraj", "HKK", "M 522,178 L 585,112 725,98 785,172 702,232 562,224 Z"),
    CzechRegion("PAK", "Pardubický kraj", "PAK", "M 562,224 L 702,232 785,172 822,252 742,312 582,322 Z"),
    CzechRegion("VYS", "Kraj Vysočina", "VYS", "M 478,382 L 582,322 742,312 782,382 682,452 542,452 Z"),
    CzechRegion("OLK", "Olomoucký kraj", "OLK", "M 702,232 L 785,172 885,188 922,272 842,332 742,312 822,252 Z"),
    CzechRegion("MSK", "Moravskoslezský kraj", "MSK", "M 785,172 L 885,118 982,158 992,252 922,272 885,188 Z"),
    CzechRegion("ZLK", "Zlínský kraj", "ZLK", "M 742,312 L 842,332 922,272 992,252 972,362 858,422 782,382 Z"),
    CzechRegion("JHM", "Jihomoravský kraj", "JHM", "M 542,452 L 682,452 782,382 858,422 838,512 678,552 428,532 Z"),
)


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
