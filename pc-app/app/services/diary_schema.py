"""Validace diary.json proti shared/schemas/diary.schema.json."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from app.config import diary_schema_path

SCHEMA_VERSION = 2
SUPPORTED_SCHEMA_VERSIONS = {1, 2}


class DiarySchemaError(ValueError):
    """Soubor neodpovídá podporované schema_version deníku."""


@lru_cache(maxsize=1)
def load_diary_schema() -> dict[str, Any]:
    path = diary_schema_path()
    return json.loads(path.read_text(encoding="utf-8"))


def diary_validator() -> Draft202012Validator:
    return Draft202012Validator(
        load_diary_schema(),
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    )


def validate_diary(data: Any) -> None:
    """Ověří deník. Neznámá schema_version i špatný tvar = odmítnout, nikdy tiše neparsovat."""
    if not isinstance(data, dict):
        raise DiarySchemaError("Deník musí být JSON objekt.")
    schema_version = data.get("schema_version")
    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        raise DiarySchemaError(
            f"Neznámá nebo nepodporovaná schema_version {schema_version!r}. "
            f"Přijímá se {sorted(SUPPORTED_SCHEMA_VERSIONS)}."
        )
    if schema_version == 2 and "trips" not in data:
        raise DiarySchemaError("Nevalidní diary.json. Verze 2 musí obsahovat pole trips.")
    errors = sorted(diary_validator().iter_errors(data), key=lambda err: list(err.absolute_path))
    if errors:
        parts: list[str] = []
        for err in errors[:8]:
            path = ".".join(str(item) for item in err.absolute_path) or "(kořen)"
            parts.append(f"{path}: {err.message}")
        raise DiarySchemaError("Nevalidní diary.json. " + " | ".join(parts))

    visits = data.get("visits")
    if isinstance(visits, list):
        ids = [item.get("id") for item in visits if isinstance(item, dict)]
        if len(ids) != len(set(ids)):
            raise DiarySchemaError("Nevalidní diary.json. Duplicitní visits[].id.")
    states = data.get("place_states")
    if isinstance(states, list):
        place_ids = [item.get("place_id") for item in states if isinstance(item, dict)]
        if len(place_ids) != len(set(place_ids)):
            raise DiarySchemaError("Nevalidní diary.json. Duplicitní place_states[].place_id.")
    trips = data.get("trips")
    if isinstance(trips, list):
        trip_ids = [item.get("id") for item in trips if isinstance(item, dict)]
        if len(trip_ids) != len(set(trip_ids)):
            raise DiarySchemaError("Nevalidní diary.json. Duplicitní trips[].id.")
    if not isinstance(data.get("trips"), list):
        data["trips"] = []


def load_and_validate_diary(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise DiarySchemaError(f"Soubor není platný JSON: {exc}") from exc
    validate_diary(data)
    if not isinstance(data, dict):
        raise DiarySchemaError("Deník musí být JSON objekt.")
    return data
