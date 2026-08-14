from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import REPO_ROOT
from app.db.models import PlaceType


def enums_path() -> Path:
    return REPO_ROOT / "shared" / "enums.json"


def seed_place_types(session: Session) -> None:
    payload = json.loads(enums_path().read_text(encoding="utf-8"))
    existing = {row.code for row in session.scalars(select(PlaceType)).all()}
    for item in payload["place_types"]:
        if item["code"] in existing:
            continue
        session.add(
            PlaceType(
                code=item["code"],
                name_cs=item["name_cs"],
                sort_order=int(item["sort_order"]),
            )
        )
    session.commit()
