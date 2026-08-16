from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.enums import items
from app.db.models import PlaceType


def seed_place_types(session: Session) -> None:
    """Doplní nové typy a synchronizuje name_cs / sort_order z shared/enums.json."""
    existing = {row.code: row for row in session.scalars(select(PlaceType)).all()}
    changed = False
    for item in items("place_types"):
        code = item["code"]
        name_cs = str(item["name_cs"])
        sort_order = int(item["sort_order"])
        row = existing.get(code)
        if row is None:
            session.add(PlaceType(code=code, name_cs=name_cs, sort_order=sort_order))
            changed = True
            continue
        if row.name_cs != name_cs or row.sort_order != sort_order:
            row.name_cs = name_cs
            row.sort_order = sort_order
            changed = True
    if changed:
        session.commit()
