"""Zobrazení názvů v PC UI. Master v DB se nemění."""


def display_place_name(name: str | None) -> str:
    trimmed = (name or "").strip()
    if not trimmed:
        return name or ""
    first = trimmed[0]
    upper = first.upper()
    if first == upper:
        return trimmed
    return f"{upper}{trimmed[1:]}"
