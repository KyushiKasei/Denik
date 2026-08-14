"""Číselníky z shared/enums.json. Kódy v datech, české popisky jen v UI."""

from __future__ import annotations

import json
from functools import lru_cache
from typing import Any

from app.config import REPO_ROOT


def enums_path():
    return REPO_ROOT / "shared" / "enums.json"


@lru_cache(maxsize=1)
def load_enums() -> dict[str, Any]:
    return json.loads(enums_path().read_text(encoding="utf-8"))


def items(group: str) -> list[dict[str, Any]]:
    return list(load_enums()[group])


def codes(group: str) -> frozenset[str]:
    return frozenset(item["code"] for item in items(group))


def label(group: str, code: str | None) -> str:
    if not code:
        return "—"
    for item in items(group):
        if item["code"] == code:
            return str(item["name_cs"])
    return code


def condition_codes() -> frozenset[str]:
    return codes("condition")


def visitability_codes() -> frozenset[str]:
    return codes("visitability")


def quality_status_codes() -> frozenset[str]:
    return codes("quality_status")


def heritage_status_codes() -> frozenset[str]:
    return codes("heritage_status")


def place_type_codes() -> frozenset[str]:
    return codes("place_types")
