"""Stejné pravidlo „za návštěvu“ jako pwa/src/catalog/visitWorth.ts."""

from __future__ import annotations

from typing import Any

from sqlalchemy import and_, exists, func, or_, select

HIDDEN_CONDITIONS = frozenset({"EXTINCT", "REMAINS"})
HIDDEN_VISITABILITY = frozenset({"EXTINCT", "CLOSED", "PRIVATE"})
STUB_VISITABILITY = frozenset({"UNKNOWN", "PRIVATE"})


def parse_worth_param(raw: str | None) -> bool | None:
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if text in {"all", "0", "false"}:
        return False
    if text in {"1", "visit", "true"}:
        return True
    return None


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _has_photo_url(photo: Any) -> bool:
    if photo is None:
        return False
    return bool(_text(getattr(photo, "thumbnail_url", None)) or _text(getattr(photo, "original_url", None)))


def place_has_catalog_image(place: Any) -> bool:
    return _has_photo_url(getattr(place, "primary_photo", None))


def place_is_worth_visiting(place: Any) -> bool:
    return is_worth_visiting(
        condition=place.condition,
        visitability=place.visitability,
        heritage_status=place.heritage_status,
        unesco=bool(place.unesco),
        has_image=place_has_catalog_image(place),
        official_website=place.official_website,
    )


def _nonempty_sql(column):
    return func.length(func.trim(func.coalesce(column, ""))) > 0


def worth_visiting_clause():
    """SQLAlchemy výraz stejný jako is_worth_visiting() / PWA."""
    from app.db.models import Place, PlacePhoto

    has_image = exists(
        select(PlacePhoto.id).where(
            PlacePhoto.place_id == Place.id,
            or_(
                _nonempty_sql(PlacePhoto.thumbnail_url),
                _nonempty_sql(PlacePhoto.original_url),
            ),
        )
    )
    weak_stub = and_(
        Place.condition == "UNKNOWN",
        Place.visitability.in_(tuple(STUB_VISITABILITY)),
        or_(Place.heritage_status.is_(None), Place.heritage_status != "NKP"),
        Place.unesco == 0,
        ~_nonempty_sql(Place.official_website),
        ~has_image,
    )
    return and_(
        Place.condition.notin_(tuple(HIDDEN_CONDITIONS)),
        Place.visitability.notin_(tuple(HIDDEN_VISITABILITY)),
        ~weak_stub,
    )


def is_weak_stub(
    *,
    condition: str,
    visitability: str,
    heritage_status: str | None = None,
    unesco: bool = False,
    has_image: bool = False,
    official_website: str | None = None,
) -> bool:
    if condition != "UNKNOWN":
        return False
    if has_image or _text(official_website):
        return False
    if heritage_status == "NKP" or unesco:
        return False
    return visitability in STUB_VISITABILITY


def is_worth_visiting(
    *,
    condition: str,
    visitability: str,
    heritage_status: str | None = None,
    unesco: bool = False,
    has_image: bool = False,
    official_website: str | None = None,
) -> bool:
    if condition in HIDDEN_CONDITIONS:
        return False
    if visitability in HIDDEN_VISITABILITY:
        return False
    if is_weak_stub(
        condition=condition,
        visitability=visitability,
        heritage_status=heritage_status,
        unesco=unesco,
        has_image=has_image,
        official_website=official_website,
    ):
        return False
    return True


def visit_score(
    *,
    condition: str,
    visitability: str,
    heritage_status: str | None = None,
    unesco: bool = False,
    has_image: bool = False,
    official_website: str | None = None,
    wikipedia_url: str | None = None,
) -> int:
    score = 0
    if unesco:
        score += 25
    if heritage_status == "NKP":
        score += 20
    elif heritage_status == "KP":
        score += 5
    if _text(official_website):
        score += 15
    if _text(wikipedia_url):
        score += 10
    if has_image:
        score += 8
    if visitability == "REGULAR":
        score += 20
    elif visitability == "SEASONAL":
        score += 15
    elif visitability == "FREE_ACCESS":
        score += 10
    elif visitability == "EXTERIOR_ONLY":
        score += 5
    elif visitability == "BY_APPOINTMENT":
        score += 3
    elif visitability == "EVENTS_ONLY":
        score += 2
    elif visitability in {"PRIVATE", "CLOSED"}:
        score -= 50
    elif visitability == "TEMPORARILY_CLOSED":
        score -= 10
    elif visitability == "EXTINCT":
        score -= 80
    if condition == "PRESERVED":
        score += 15
    elif condition == "REBUILT":
        score += 12
    elif condition == "RUIN":
        score += 8
    elif condition == "REMAINS":
        score -= 25
    elif condition == "EXTINCT":
        score -= 80
    return score
