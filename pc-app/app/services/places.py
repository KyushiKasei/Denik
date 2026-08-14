"""CRUD a filtry master katalogu. Nemění Place.public_id, nemaže fyzicky."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlencode

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session
from starlette.datastructures import FormData, QueryParams

from app.db.enums import (
    condition_codes,
    heritage_status_codes,
    items,
    label,
    place_type_codes,
    quality_status_codes,
    visitability_codes,
)
from app.db.models import Place, PlacePlaceType, PlaceType, now_iso
from app.logging_setup import get_logger

PAGE_SIZE = 50
SORT_CHOICES = {
    "name": "Název A–Z",
    "name_desc": "Název Z–A",
    "municipality": "Obec",
    "region": "Kraj",
    "updated": "Naposledy upraveno",
}

_log = get_logger()


def _blank_to_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def parse_alternative_names(text: str | None) -> list[str]:
    if not text:
        return []
    seen: set[str] = set()
    names: list[str] = []
    for line in str(text).splitlines():
        name = line.strip()
        if not name or name in seen:
            continue
        seen.add(name)
        names.append(name)
    return names


def dump_alternative_names(names: list[str]) -> str:
    return json.dumps(names, ensure_ascii=False)


def parse_coord(raw: Any, kind: str) -> tuple[float | None, str | None]:
    text = _blank_to_none(raw)
    if text is None:
        return None, None
    normalized = text.replace(",", ".")
    try:
        value = float(normalized)
    except ValueError:
        word = "šířka" if kind == "latitude" else "délka"
        return None, f"Neplatné číslo zeměpisné {word}."
    if kind == "latitude" and not -90.0 <= value <= 90.0:
        return None, "Zeměpisná šířka musí být mezi −90 a 90."
    if kind == "longitude" and not -180.0 <= value <= 180.0:
        return None, "Zeměpisná délka musí být mezi −180 a 180."
    return value, None


def parse_url(raw: Any) -> tuple[str | None, str | None]:
    text = _blank_to_none(raw)
    if text is None:
        return None, None
    if not (text.startswith("http://") or text.startswith("https://")):
        return None, "URL musí začínat http:// nebo https://"
    return text, None


@dataclass
class PlaceInput:
    name: str = ""
    short_name: str | None = None
    alternative_names: list[str] = field(default_factory=list)
    type_codes: list[str] = field(default_factory=list)
    condition: str = "UNKNOWN"
    visitability: str = "UNKNOWN"
    quality_status: str = "VERIFIED"
    heritage_status: str | None = None
    unesco: bool = False
    latitude: float | None = None
    longitude: float | None = None
    address: str | None = None
    municipality: str | None = None
    municipality_code: str | None = None
    district: str | None = None
    district_code: str | None = None
    region: str | None = None
    region_code: str | None = None
    country: str = "CZ"
    short_description: str | None = None
    official_website: str | None = None
    wikipedia_url: str | None = None
    opening_hours_url: str | None = None
    ticket_url: str | None = None
    errors: dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_form(cls, form: FormData) -> PlaceInput:
        data = cls()
        data.name = str(form.get("name") or "").strip()
        data.short_name = _blank_to_none(form.get("short_name"))
        data.alternative_names = parse_alternative_names(str(form.get("alternative_names") or ""))
        data.type_codes = [str(code) for code in form.getlist("type_codes") if str(code).strip()]
        data.condition = str(form.get("condition") or "UNKNOWN").strip()
        data.visitability = str(form.get("visitability") or "UNKNOWN").strip()
        data.quality_status = str(form.get("quality_status") or "VERIFIED").strip()
        data.heritage_status = _blank_to_none(form.get("heritage_status"))
        data.unesco = str(form.get("unesco") or "") in {"1", "on", "true", "yes"}
        data.address = _blank_to_none(form.get("address"))
        data.municipality = _blank_to_none(form.get("municipality"))
        data.municipality_code = _blank_to_none(form.get("municipality_code"))
        data.district = _blank_to_none(form.get("district"))
        data.district_code = _blank_to_none(form.get("district_code"))
        data.region = _blank_to_none(form.get("region"))
        data.region_code = _blank_to_none(form.get("region_code"))
        data.country = (_blank_to_none(form.get("country")) or "CZ").upper()
        data.short_description = _blank_to_none(form.get("short_description"))

        lat, lat_err = parse_coord(form.get("latitude"), "latitude")
        lon, lon_err = parse_coord(form.get("longitude"), "longitude")
        data.latitude = lat
        data.longitude = lon
        if lat_err:
            data.errors["latitude"] = lat_err
        if lon_err:
            data.errors["longitude"] = lon_err

        for field_name, raw in (
            ("official_website", form.get("official_website")),
            ("wikipedia_url", form.get("wikipedia_url")),
            ("opening_hours_url", form.get("opening_hours_url")),
            ("ticket_url", form.get("ticket_url")),
        ):
            value, err = parse_url(raw)
            setattr(data, field_name, value)
            if err:
                data.errors[field_name] = err
        return data

    @classmethod
    def from_place(cls, place: Place) -> PlaceInput:
        return cls(
            name=place.name,
            short_name=place.short_name,
            alternative_names=place.alt_names,
            type_codes=[item.code for item in place.types],
            condition=place.condition,
            visitability=place.visitability,
            quality_status=place.quality_status,
            heritage_status=place.heritage_status,
            unesco=bool(place.unesco),
            latitude=place.latitude,
            longitude=place.longitude,
            address=place.address,
            municipality=place.municipality,
            municipality_code=place.municipality_code,
            district=place.district,
            district_code=place.district_code,
            region=place.region,
            region_code=place.region_code,
            country=place.country,
            short_description=place.short_description,
            official_website=place.official_website,
            wikipedia_url=place.wikipedia_url,
            opening_hours_url=place.opening_hours_url,
            ticket_url=place.ticket_url,
        )

    def alternative_names_text(self) -> str:
        return "\n".join(self.alternative_names)

    def validate(self) -> bool:
        if not self.name:
            self.errors["name"] = "Název je povinný."
        if self.condition not in condition_codes():
            self.errors["condition"] = "Neznámý stav objektu."
        if self.visitability not in visitability_codes():
            self.errors["visitability"] = "Neznámá přístupnost."
        if self.quality_status not in quality_status_codes():
            self.errors["quality_status"] = "Neznámý stav kvality."
        if self.heritage_status and self.heritage_status not in heritage_status_codes():
            self.errors["heritage_status"] = "Neznámý památkový status."
        unknown_types = [code for code in self.type_codes if code not in place_type_codes()]
        if unknown_types:
            self.errors["type_codes"] = "Neznámý typ památky."
        if (self.latitude is None) != (self.longitude is None):
            self.errors["coordinates"] = "Zadejte obě souřadnice, nebo ani jednu."
        if len(self.country) > 8:
            self.errors["country"] = "Kód země je příliš dlouhý."
        return not self.errors


@dataclass
class PlaceFilters:
    q: str = ""
    type_code: str = ""
    region: str = ""
    district: str = ""
    municipality: str = ""
    condition: str = ""
    visitability: str = ""
    quality_status: str = ""
    missing_gps: bool = False
    missing_type: bool = False
    archived: str = "active"
    sort: str = "name"
    page: int = 1

    @classmethod
    def from_query(cls, params: QueryParams) -> PlaceFilters:
        try:
            page = int(params.get("page") or 1)
        except ValueError:
            page = 1
        archived = params.get("archived") or "active"
        if archived not in {"active", "archived", "all"}:
            archived = "active"
        sort = params.get("sort") or "name"
        if sort not in SORT_CHOICES:
            sort = "name"
        return cls(
            q=(params.get("q") or "").strip(),
            type_code=(params.get("type") or "").strip(),
            region=(params.get("region") or "").strip(),
            district=(params.get("district") or "").strip(),
            municipality=(params.get("municipality") or "").strip(),
            condition=(params.get("condition") or "").strip(),
            visitability=(params.get("visitability") or "").strip(),
            quality_status=(params.get("quality_status") or "").strip(),
            missing_gps=params.get("missing_gps") in {"1", "on", "true"},
            missing_type=params.get("missing_type") in {"1", "on", "true"},
            archived=archived,
            sort=sort,
            page=max(page, 1),
        )

    def query_string(self, page: int | None = None) -> str:
        pairs: list[tuple[str, str]] = []
        if self.q:
            pairs.append(("q", self.q))
        if self.type_code:
            pairs.append(("type", self.type_code))
        if self.region:
            pairs.append(("region", self.region))
        if self.district:
            pairs.append(("district", self.district))
        if self.municipality:
            pairs.append(("municipality", self.municipality))
        if self.condition:
            pairs.append(("condition", self.condition))
        if self.visitability:
            pairs.append(("visitability", self.visitability))
        if self.quality_status:
            pairs.append(("quality_status", self.quality_status))
        if self.missing_gps:
            pairs.append(("missing_gps", "1"))
        if self.missing_type:
            pairs.append(("missing_type", "1"))
        if self.archived != "active":
            pairs.append(("archived", self.archived))
        if self.sort != "name":
            pairs.append(("sort", self.sort))
        shown_page = self.page if page is None else page
        if shown_page > 1:
            pairs.append(("page", str(shown_page)))
        return urlencode(pairs)


@dataclass
class PlaceListResult:
    places: list[Place]
    total: int
    page: int
    pages: int
    per_page: int


def _apply_filters(stmt, filters: PlaceFilters):
    if filters.archived == "active":
        stmt = stmt.where(Place.archived_at.is_(None))
    elif filters.archived == "archived":
        stmt = stmt.where(Place.archived_at.is_not(None))

    if filters.q:
        term = f"%{filters.q}%"
        stmt = stmt.where(
            or_(
                Place.name.ilike(term),
                Place.short_name.ilike(term),
                Place.alternative_names.ilike(term),
                Place.municipality.ilike(term),
                Place.district.ilike(term),
                Place.region.ilike(term),
            )
        )
    if filters.type_code:
        stmt = stmt.where(
            Place.id.in_(
                select(PlacePlaceType.place_id)
                .join(PlaceType, PlaceType.id == PlacePlaceType.place_type_id)
                .where(PlaceType.code == filters.type_code)
            )
        )
    if filters.region:
        stmt = stmt.where(Place.region == filters.region)
    if filters.district:
        stmt = stmt.where(Place.district == filters.district)
    if filters.municipality:
        stmt = stmt.where(Place.municipality == filters.municipality)
    if filters.condition:
        stmt = stmt.where(Place.condition == filters.condition)
    if filters.visitability:
        stmt = stmt.where(Place.visitability == filters.visitability)
    if filters.quality_status:
        stmt = stmt.where(Place.quality_status == filters.quality_status)
    if filters.missing_gps:
        stmt = stmt.where(or_(Place.latitude.is_(None), Place.longitude.is_(None)))
    if filters.missing_type:
        stmt = stmt.where(~exists(select(PlacePlaceType.place_id).where(PlacePlaceType.place_id == Place.id)))
    return stmt


def _order_clause(sort: str):
    if sort == "name_desc":
        return Place.name.desc()
    if sort == "municipality":
        return Place.municipality.asc()
    if sort == "region":
        return Place.region.asc()
    if sort == "updated":
        return Place.updated_at.desc()
    return Place.name.asc()


def list_places(session: Session, filters: PlaceFilters) -> PlaceListResult:
    stmt = _apply_filters(select(Place), filters)
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE) if total else 1
    page = min(filters.page, pages)
    rows = session.scalars(
        stmt.order_by(_order_clause(filters.sort), Place.id.asc())
        .offset((page - 1) * PAGE_SIZE)
        .limit(PAGE_SIZE)
    ).all()
    return PlaceListResult(places=list(rows), total=total, page=page, pages=pages, per_page=PAGE_SIZE)


def distinct_locations(session: Session) -> dict[str, list[str]]:
    def values(column) -> list[str]:
        rows = session.scalars(
            select(column)
            .where(column.is_not(None), column != "")
            .distinct()
            .order_by(column.asc())
        ).all()
        return [str(item) for item in rows]

    return {
        "regions": values(Place.region),
        "districts": values(Place.district),
        "municipalities": values(Place.municipality),
    }


def all_place_types(session: Session) -> list[PlaceType]:
    return list(session.scalars(select(PlaceType).order_by(PlaceType.sort_order, PlaceType.id)).all())


def get_place_by_public_id(session: Session, public_id: str) -> Place | None:
    return session.scalar(select(Place).where(Place.public_id == public_id))


def _types_for_codes(session: Session, codes: list[str]) -> list[PlaceType]:
    if not codes:
        return []
    found = list(session.scalars(select(PlaceType).where(PlaceType.code.in_(codes))).all())
    by_code = {item.code: item for item in found}
    return [by_code[code] for code in codes if code in by_code]


def _apply_input(place: Place, data: PlaceInput, session: Session) -> None:
    place.name = data.name
    place.short_name = data.short_name
    place.alternative_names = dump_alternative_names(data.alternative_names)
    place.condition = data.condition
    place.visitability = data.visitability
    place.quality_status = data.quality_status
    place.heritage_status = data.heritage_status
    place.unesco = 1 if data.unesco else 0
    place.latitude = data.latitude
    place.longitude = data.longitude
    place.address = data.address
    place.municipality = data.municipality
    place.municipality_code = data.municipality_code
    place.district = data.district
    place.district_code = data.district_code
    place.region = data.region
    place.region_code = data.region_code
    place.country = data.country
    place.short_description = data.short_description
    place.official_website = data.official_website
    place.wikipedia_url = data.wikipedia_url
    place.opening_hours_url = data.opening_hours_url
    place.ticket_url = data.ticket_url
    place.types = _types_for_codes(session, data.type_codes)
    place.updated_at = now_iso()


def create_place(session: Session, data: PlaceInput) -> Place:
    if not data.validate():
        raise ValueError("PlaceInput is invalid")
    place = Place(name=data.name)
    session.add(place)
    session.flush()
    _apply_input(place, data, session)
    session.commit()
    session.refresh(place)
    _log.info("place created public_id=%s name=%s", place.public_id, place.name)
    return place


def update_place(session: Session, place: Place, data: PlaceInput) -> Place:
    if not data.validate():
        raise ValueError("PlaceInput is invalid")
    public_id = place.public_id
    _apply_input(place, data, session)
    if place.public_id != public_id:
        raise ValueError("Place.public_id is immutable and must never be changed")
    session.commit()
    session.refresh(place)
    _log.info("place updated public_id=%s name=%s", place.public_id, place.name)
    return place


def archive_place(session: Session, place: Place) -> Place:
    if place.archived_at is None:
        place.archived_at = now_iso()
        place.updated_at = place.archived_at
        session.commit()
        session.refresh(place)
        _log.info("place archived public_id=%s name=%s", place.public_id, place.name)
    return place


def restore_place(session: Session, place: Place) -> Place:
    if place.archived_at is not None:
        place.archived_at = None
        place.updated_at = now_iso()
        session.commit()
        session.refresh(place)
        _log.info("place restored public_id=%s name=%s", place.public_id, place.name)
    return place


@dataclass
class TypeStat:
    code: str
    name_cs: str
    count: int


@dataclass
class DashboardStats:
    total_active: int
    total_archived: int
    total_all: int
    verified: int
    needs_review: int
    missing_gps: int
    missing_type: int
    by_type: list[TypeStat]


def dashboard_stats(session: Session) -> DashboardStats:
    active = Place.archived_at.is_(None)
    total_all = session.scalar(select(func.count()).select_from(Place)) or 0
    total_archived = session.scalar(select(func.count()).select_from(Place).where(Place.archived_at.is_not(None))) or 0
    total_active = total_all - total_archived
    verified = session.scalar(
        select(func.count()).select_from(Place).where(active, Place.quality_status == "VERIFIED")
    ) or 0
    needs_review = session.scalar(
        select(func.count()).select_from(Place).where(active, Place.quality_status == "NEEDS_REVIEW")
    ) or 0
    missing_gps = session.scalar(
        select(func.count())
        .select_from(Place)
        .where(active, or_(Place.latitude.is_(None), Place.longitude.is_(None)))
    ) or 0
    missing_type = session.scalar(
        select(func.count())
        .select_from(Place)
        .where(active, ~exists(select(PlacePlaceType.place_id).where(PlacePlaceType.place_id == Place.id)))
    ) or 0

    type_rows = session.execute(
        select(PlaceType.code, PlaceType.name_cs, func.count(Place.id))
        .select_from(PlaceType)
        .outerjoin(PlacePlaceType, PlacePlaceType.place_type_id == PlaceType.id)
        .outerjoin(Place, (Place.id == PlacePlaceType.place_id) & active)
        .group_by(PlaceType.id)
        .order_by(PlaceType.sort_order, PlaceType.id)
    ).all()
    by_type = [TypeStat(code=row[0], name_cs=row[1], count=int(row[2])) for row in type_rows]
    return DashboardStats(
        total_active=total_active,
        total_archived=total_archived,
        total_all=total_all,
        verified=verified,
        needs_review=needs_review,
        missing_gps=missing_gps,
        missing_type=missing_type,
        by_type=by_type,
    )


def form_context() -> dict[str, Any]:
    return {
        "conditions": items("condition"),
        "visitabilities": items("visitability"),
        "quality_statuses": items("quality_status"),
        "heritage_statuses": items("heritage_status"),
        "enum_label": label,
    }
