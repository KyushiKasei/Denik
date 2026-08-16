"""Stabilní UUIDv7 pro Place.public_id a Visit.public_id."""

from __future__ import annotations

try:
    from uuid import uuid7 as _uuid7
except ImportError:  # Python < 3.13
    from uuid_utils import uuid7 as _uuid7


def new_public_id() -> str:
    """Vrátí nový UUIDv7. Nikdy ho neodvozuj z externího ID."""
    return str(_uuid7())
