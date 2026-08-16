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


def format_types(codes: list[str]) -> str:
    """Stejné skládání jako pwa/src/catalog/labels.ts formatTypes (PLAN: hrad a zámek)."""
    names = [label("place_types", code) for code in codes if code]
    if not names:
        return "Bez typu"
    if len(names) == 2:
        return f"{names[0]} a {names[1].lower()}"
    return ", ".join(names)


VISITABILITY_FORM_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("Přístupné veřejnosti", ("REGULAR", "SEASONAL", "FREE_ACCESS")),
    ("Omezené", ("BY_APPOINTMENT", "EVENTS_ONLY", "EXTERIOR_ONLY")),
    ("Nepřístupné", ("PRIVATE", "TEMPORARILY_CLOSED", "CLOSED", "EXTINCT")),
    ("Nezařazené", ("UNKNOWN",)),
)


def visitability_filter_codes(value: str) -> frozenset[str]:
    if not value:
        return frozenset()
    for group in items("visitability_filter_groups"):
        if group["code"] == value:
            return frozenset(group["codes"])
    return frozenset({value})


def visitability_form_groups() -> list[dict[str, Any]]:
    by_code = {item["code"]: item for item in items("visitability")}
    groups: list[dict[str, Any]] = []
    for group_label, group_codes in VISITABILITY_FORM_GROUPS:
        group_items = [by_code[code] for code in group_codes if code in by_code]
        if group_items:
            groups.append({"label": group_label, "options": group_items})
    return groups


def condition_codes() -> frozenset[str]:
    return codes("condition")


def visitability_codes() -> frozenset[str]:
    return codes("visitability")


def quality_status_codes() -> frozenset[str]:
    return codes("quality_status")


def heritage_status_codes() -> frozenset[str]:
    return codes("heritage_status")


def source_type_codes() -> frozenset[str]:
    return codes("source_types")


def place_type_codes() -> frozenset[str]:
    return codes("place_types")
