"""Validace catalog.json proti shared/schemas/catalog.schema.json."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from app.config import catalog_schema_path

SCHEMA_VERSION = 1


class CatalogSchemaError(ValueError):
    """Soubor neodpovídá schema_version 1."""


@lru_cache(maxsize=1)
def load_catalog_schema() -> dict[str, Any]:
    path = catalog_schema_path()
    return json.loads(path.read_text(encoding="utf-8"))


def catalog_validator() -> Draft202012Validator:
    return Draft202012Validator(
        load_catalog_schema(),
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    )


def validate_catalog(data: Any) -> None:
    """Ověří katalog. Neznámá schema_version i špatný tvar = odmítnout, nikdy tiše neparsovat."""
    if not isinstance(data, dict):
        raise CatalogSchemaError("Katalog musí být JSON objekt.")
    schema_version = data.get("schema_version")
    if schema_version != SCHEMA_VERSION:
        raise CatalogSchemaError(
            f"Neznámá nebo nepodporovaná schema_version {schema_version!r}. "
            f"MVP přijímá jen {SCHEMA_VERSION}."
        )
    errors = sorted(catalog_validator().iter_errors(data), key=lambda err: list(err.absolute_path))
    if errors:
        parts: list[str] = []
        for err in errors[:8]:
            path = ".".join(str(item) for item in err.absolute_path) or "(kořen)"
            parts.append(f"{path}: {err.message}")
        raise CatalogSchemaError("Nevalidní catalog.json. " + " | ".join(parts))

    places = data.get("places")
    if isinstance(places, list):
        ids = [item.get("id") for item in places if isinstance(item, dict)]
        if len(ids) != len(set(ids)):
            raise CatalogSchemaError("Nevalidní catalog.json. Duplicitní places[].id.")


def load_and_validate_catalog(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise CatalogSchemaError(f"Soubor není platný JSON: {exc}") from exc
    validate_catalog(data)
    if not isinstance(data, dict):
        raise CatalogSchemaError("Katalog musí být JSON objekt.")
    return data
