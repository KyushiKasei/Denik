"""Ochrana ručních změn master polí (place_field_overrides)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ImportFieldChange, Place, PlaceFieldOverride, now_iso
from app.services.values import decode_value, encode_value, values_equal

OVERRIDEABLE_FIELDS = (
    "name",
    "short_name",
    "alternative_names",
    "short_description",
    "condition",
    "visitability",
    "quality_status",
    "heritage_status",
    "unesco",
    "latitude",
    "longitude",
    "address",
    "municipality",
    "municipality_code",
    "district",
    "district_code",
    "region",
    "region_code",
    "country",
    "official_website",
    "wikipedia_url",
    "opening_hours_url",
    "ticket_url",
    "osm_opening_hours",
    "phone",
    "fee",
    "wheelchair",
    "parking",
    "visit_duration_minutes",
    "last_entry",
    "dogs",
    "payment",
    "amenities",
    "inception_year",
    "architectural_style",
    "types",
)

FIELD_LABELS_CS = {
    "name": "Název",
    "short_name": "Krátký název",
    "alternative_names": "Další názvy",
    "short_description": "Popis",
    "condition": "Stav objektu",
    "visitability": "Přístupnost",
    "quality_status": "Kvalita dat",
    "heritage_status": "Památková ochrana",
    "unesco": "UNESCO",
    "latitude": "Zeměpisná šířka",
    "longitude": "Zeměpisná délka",
    "address": "Adresa",
    "municipality": "Obec",
    "municipality_code": "Kód obce",
    "district": "Okres",
    "district_code": "Kód okresu",
    "region": "Kraj",
    "region_code": "Kód kraje",
    "country": "Země",
    "official_website": "Oficiální web",
    "wikipedia_url": "Wikipedia",
    "opening_hours_url": "Otevírací doba",
    "ticket_url": "Vstupenky",
    "osm_opening_hours": "OSM hodiny",
    "phone": "Telefon",
    "fee": "Vstupné",
    "wheelchair": "Bezbariérovost",
    "parking": "Parkování",
    "visit_duration_minutes": "Délka prohlídky (min)",
    "last_entry": "Poslední vstup",
    "dogs": "Psi",
    "payment": "Platba",
    "amenities": "Zázemí",
    "inception_year": "Rok vzniku",
    "architectural_style": "Sloh",
    "types": "Typy",
}


def snapshot_place(place: Place) -> dict[str, Any]:
    return {
        "name": place.name,
        "short_name": place.short_name,
        "alternative_names": place.alt_names,
        "short_description": place.short_description,
        "condition": place.condition,
        "visitability": place.visitability,
        "quality_status": place.quality_status,
        "heritage_status": place.heritage_status,
        "unesco": int(place.unesco or 0),
        "latitude": place.latitude,
        "longitude": place.longitude,
        "address": place.address,
        "municipality": place.municipality,
        "municipality_code": place.municipality_code,
        "district": place.district,
        "district_code": place.district_code,
        "region": place.region,
        "region_code": place.region_code,
        "country": place.country,
        "official_website": place.official_website,
        "wikipedia_url": place.wikipedia_url,
        "opening_hours_url": place.opening_hours_url,
        "ticket_url": place.ticket_url,
        "osm_opening_hours": place.osm_opening_hours,
        "phone": place.phone,
        "fee": place.fee,
        "wheelchair": place.wheelchair,
        "parking": place.parking,
        "visit_duration_minutes": place.visit_duration_minutes,
        "last_entry": place.last_entry,
        "dogs": place.dogs,
        "payment": place.payment,
        "amenities": place.amenity_codes,
        "inception_year": place.inception_year,
        "architectural_style": place.architectural_style,
        "types": [item.code for item in place.types],
    }


def master_value(place: Place, field_name: str) -> Any:
    return snapshot_place(place).get(field_name)


def get_override(session: Session, place_id: int, field_name: str) -> PlaceFieldOverride | None:
    return session.get(PlaceFieldOverride, (place_id, field_name))


def has_override(session: Session, place_id: int, field_name: str) -> bool:
    return get_override(session, place_id, field_name) is not None


def upsert_override(
    session: Session,
    place: Place,
    field_name: str,
    value: Any,
    note: str | None = None,
) -> PlaceFieldOverride:
    row = get_override(session, place.id, field_name)
    encoded = encode_value(value)
    now = now_iso()
    if row is None:
        row = PlaceFieldOverride(
            place_id=place.id,
            field_name=field_name,
            value_json=encoded,
            note=note,
            created_at=now,
            updated_at=now,
        )
        session.add(row)
    else:
        row.value_json = encoded
        row.updated_at = now
        if note is not None:
            row.note = note
    return row


def delete_override(session: Session, place_id: int, field_name: str) -> None:
    row = get_override(session, place_id, field_name)
    if row is not None:
        session.delete(row)


def record_manual_edits(session: Session, place: Place, before: dict[str, Any]) -> list[str]:
    """Po ruční úpravě v UI zapíše override pro každé změněné pole."""
    after = snapshot_place(place)
    changed: list[str] = []
    for field_name in OVERRIDEABLE_FIELDS:
        if not values_equal(before.get(field_name), after.get(field_name)):
            upsert_override(session, place, field_name, after.get(field_name), note="Ruční úprava v katalogu")
            changed.append(field_name)
    return changed


def apply_value_to_place(place: Place, field_name: str, value: Any, session: Session) -> None:
    if field_name == "types":
        from app.db.models import PlaceType

        codes = [str(code) for code in (value or [])]
        found = list(session.scalars(select(PlaceType).where(PlaceType.code.in_(codes))).all()) if codes else []
        by_code = {item.code: item for item in found}
        place.types = [by_code[code] for code in codes if code in by_code]
        return
    if field_name == "alternative_names":
        place.alternative_names = encode_value(value if isinstance(value, list) else [])
        return
    if field_name == "amenities":
        codes = [str(item) for item in (value or []) if str(item) in {"toilets", "cafe", "playground"}]
        place.amenities = encode_value(list(dict.fromkeys(codes)))
        return
    if field_name == "unesco":
        place.unesco = 1 if value in (1, True, "1", "true") else 0
        return
    if hasattr(place, field_name):
        setattr(place, field_name, value)


def keep_master(session: Session, change: ImportFieldChange) -> ImportFieldChange:
    change.status = "keep_master"
    change.resolved_at = now_iso()
    return change


def take_source(session: Session, change: ImportFieldChange) -> ImportFieldChange:
    place = session.get(Place, change.place_id)
    if place is None:
        raise ValueError("Place for field change not found")
    new_value = decode_value(change.new_source_value)
    apply_value_to_place(place, change.field_name, new_value, session)
    delete_override(session, place.id, change.field_name)
    place.updated_at = now_iso()
    change.status = "take_source"
    change.resolved_at = now_iso()
    return change
