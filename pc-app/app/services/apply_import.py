"""Aplikace kanonických záznamů: preview, apply, záloha, transakce, review."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.db.models import (
    ImportFieldChange,
    ImportReview,
    ImportReviewCandidate,
    ImportRun,
    Place,
    PlacePhoto,
    PlaceSource,
    PlaceSourceValue,
    PlaceType,
    now_iso,
)
from app.importers.base import CanonicalRecord
from app.logging_setup import get_logger
from app.services.backup import backup_before_import
from app.services.import_progress import data_dir_for_session, write_progress
from app.services.matching import (
    LEVEL_B,
    LEVEL_FAILED,
    LEVEL_IGNORED,
    MatchDecision,
    MatchIndex,
    match_record,
)
from app.services.overrides import (
    apply_value_to_place,
    has_override,
    master_value,
)
from app.services.source_urls import identity_source_url
from app.services.values import decode_value, encode_value, values_equal

_log = get_logger()

SOURCE_VALUE_FIELDS = (
    "name",
    "alternative_names",
    "types",
    "condition",
    "visitability",
    "latitude",
    "longitude",
    "address",
    "municipality",
    "district",
    "region",
    "short_description",
    "official_website",
    "wikipedia_url",
    "heritage_status",
    "municipality_code",
    "district_code",
    "region_code",
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
    "unesco",
)

FIELD_SOURCE_PRIORITY: dict[str, list[str]] = {
    "heritage_status": ["pamatkovy_katalog", "uskp"],
    "unesco": ["pamatkovy_katalog", "uskp"],
    "municipality": ["ruian", "pamatkovy_katalog", "wikidata"],
    "district": ["ruian", "pamatkovy_katalog", "wikidata"],
    "region": ["ruian", "pamatkovy_katalog", "wikidata"],
    "municipality_code": ["ruian", "pamatkovy_katalog", "wikidata"],
    "district_code": ["ruian", "pamatkovy_katalog", "wikidata"],
    "region_code": ["ruian", "pamatkovy_katalog", "wikidata"],
    "latitude": ["pamatkovy_katalog", "wikidata", "osm"],
    "longitude": ["pamatkovy_katalog", "wikidata", "osm"],
    "name": ["wikidata"],
    "official_website": ["npu", "wikidata", "osm"],
    "wikipedia_url": ["wikipedia", "wikidata"],
    "short_description": ["wikidata", "pamatkovy_katalog"],
    "address": ["pamatkovy_katalog", "wikidata", "osm", "ruian"],
    "opening_hours_url": ["npu", "official_web", "osm"],
    "ticket_url": ["npu", "official_web"],
    "osm_opening_hours": ["osm"],
    "phone": ["osm"],
    "fee": ["osm"],
    "wheelchair": ["osm"],
    "parking": ["osm"],
    "visit_duration_minutes": ["osm"],
    "last_entry": ["osm"],
    "dogs": ["osm"],
    "payment": ["osm"],
    "amenities": ["osm"],
    "inception_year": ["wikidata"],
    "architectural_style": ["wikidata"],
    "visitability": ["npu", "osm", "official_web", "wikidata"],
    "condition": ["wikidata", "osm"],
}


@dataclass
class RecordOutcome:
    name: str
    level: str
    action: str
    reason: str
    public_id: str | None = None
    candidate_names: list[str] = field(default_factory=list)


@dataclass
class ImportResult:
    run_id: int | None
    status: str
    source_type: str
    backup_path: str | None
    records_received: int = 0
    records_created: int = 0
    records_updated: int = 0
    records_unchanged: int = 0
    records_review: int = 0
    records_failed: int = 0
    records_ignored: int = 0
    log: str = ""
    outcomes: list[RecordOutcome] = field(default_factory=list)
    error: str | None = None

    def counts_ok(self) -> bool:
        counted = (
            self.records_created
            + self.records_updated
            + self.records_unchanged
            + self.records_review
            + self.records_ignored
            + self.records_failed
        )
        return counted == self.records_received


def record_field_value(record: CanonicalRecord, field_name: str) -> Any:
    if field_name == "types":
        return list(record.types)
    if field_name == "alternative_names":
        return list(record.alternative_names)
    if field_name == "amenities":
        return list(record.amenities)
    if field_name == "unesco":
        if record.unesco is None:
            return None
        return 1 if record.unesco else 0
    return getattr(record, field_name, None)


def _source_rank(field_name: str, source_type: str) -> int:
    ranking = FIELD_SOURCE_PRIORITY.get(field_name)
    if ranking is None:
        return 0
    try:
        return ranking.index(source_type)
    except ValueError:
        return 100


def _sources_claiming_field(session: Session, place_id: int, field_name: str) -> list[str]:
    rows = session.execute(
        select(PlaceSource.source_type)
        .join(PlaceSourceValue, PlaceSourceValue.place_source_id == PlaceSource.id)
        .where(PlaceSource.place_id == place_id, PlaceSourceValue.field_name == field_name)
    ).all()
    return [row[0] for row in rows]


def source_may_write_master(session: Session, place: Place, field_name: str, incoming_source: str) -> bool:
    ranking = FIELD_SOURCE_PRIORITY.get(field_name)
    if ranking is None:
        return True
    existing = _sources_claiming_field(session, place.id, field_name)
    if not existing:
        return True
    incoming_rank = _source_rank(field_name, incoming_source)
    best_existing = min(_source_rank(field_name, item) for item in existing)
    return incoming_rank <= best_existing


def _types_for_codes(session: Session, codes: list[str]) -> list[PlaceType]:
    if not codes:
        return []
    found = list(session.scalars(select(PlaceType).where(PlaceType.code.in_(codes))).all())
    by_code = {item.code: item for item in found}
    return [by_code[code] for code in codes if code in by_code]


def _merge_alt_names(place: Place, incoming: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for name in [*place.alt_names, *incoming]:
        text = str(name).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        out.append(text)
    return out


def _lookup_source(
    session: Session,
    source_type: str,
    external_id: str | None,
    *,
    place_id: int | None = None,
) -> PlaceSource | None:
    if external_id:
        return session.scalar(
            select(PlaceSource).where(
                PlaceSource.source_type == source_type,
                PlaceSource.external_id == external_id,
            )
        )
    if place_id is None:
        return None
    return session.scalar(
        select(PlaceSource).where(
            PlaceSource.source_type == source_type,
            PlaceSource.place_id == place_id,
            or_(PlaceSource.external_id.is_(None), PlaceSource.external_id == ""),
        )
    )


def _page_url_for(source_type: str, external_id: str | None, record: CanonicalRecord, *, with_values: bool) -> str | None:
    built = identity_source_url(source_type, external_id)
    if built:
        return built
    if with_values:
        return record.source_url
    return None


def _ensure_source(
    session: Session,
    place: Place,
    source_type: str,
    external_id: str | None,
    record: CanonicalRecord,
    *,
    with_values: bool,
) -> tuple[PlaceSource, bool]:
    """Vrátí (source, changed)."""
    existing = _lookup_source(session, source_type, external_id, place_id=place.id)
    now = now_iso()
    raw = json.dumps(record.to_dict(), ensure_ascii=False, default=str)
    page_url = _page_url_for(source_type, external_id, record, with_values=with_values)
    created = existing is None
    if existing is None:
        source = PlaceSource(
            place_id=place.id,
            source_type=source_type,
            external_id=external_id or None,
            source_url=page_url,
            fetched_at=record.fetched_at or now,
            license=record.license,
            raw_data=raw,
            created_at=now,
            updated_at=now,
        )
        session.add(source)
        session.flush()
    else:
        if existing.place_id != place.id:
            raise RuntimeError(
                f"Externí ID {source_type}/{external_id} patří jinému Place (id={existing.place_id})"
            )
        source = existing
        # Identita z jiného zdroje (RÚIAN nese wikidata/osm ID) nesmí přepsat cizí raw.
        if with_values:
            source.raw_data = raw
            if page_url:
                source.source_url = page_url
            source.fetched_at = record.fetched_at or now
            source.license = record.license or source.license
            source.updated_at = now
    values_changed = False
    if with_values:
        values_changed = _sync_source_values(session, source, record)
    return source, created or values_changed


def _sync_source_values(session: Session, source: PlaceSource, record: CanonicalRecord) -> bool:
    changed = False
    fetched = record.fetched_at or now_iso()
    for field_name in SOURCE_VALUE_FIELDS:
        value = record_field_value(record, field_name)
        if value is None or value == [] or value == "":
            continue
        encoded = encode_value(value)
        row = session.scalar(
            select(PlaceSourceValue).where(
                PlaceSourceValue.place_source_id == source.id,
                PlaceSourceValue.field_name == field_name,
            )
        )
        if row is None:
            session.add(
                PlaceSourceValue(
                    place_source_id=source.id,
                    field_name=field_name,
                    value_json=encoded,
                    fetched_at=fetched,
                )
            )
            changed = True
        elif row.value_json != encoded:
            row.value_json = encoded
            row.fetched_at = fetched
            changed = True
    return changed


def _old_source_value(session: Session, source: PlaceSource, field_name: str) -> Any:
    row = session.scalar(
        select(PlaceSourceValue).where(
            PlaceSourceValue.place_source_id == source.id,
            PlaceSourceValue.field_name == field_name,
        )
    )
    return decode_value(row.value_json) if row else None


def _attach_identities(session: Session, place: Place, record: CanonicalRecord) -> bool:
    changed = False
    _, source_changed = _ensure_source(
        session, place, record.source_type, record.external_id, record, with_values=True
    )
    changed = changed or source_changed
    primary = (record.source_type, record.external_id)
    for source_type, external_id in record.all_external_ids():
        if (source_type, external_id) == primary:
            continue
        _, extra_changed = _ensure_source(
            session, place, source_type, external_id, record, with_values=False
        )
        if extra_changed:
            changed = True
    return changed


def _photo_filename_hint(image: dict[str, Any]) -> str:
    raw = str(image.get("filename") or "")
    return raw.replace(" ", "_")


def _find_existing_photo(session: Session, place: Place, image: dict[str, Any]) -> PlacePhoto | None:
    original = image.get("original_url") or image.get("source_url")
    thumb = image.get("thumbnail_url")
    if original:
        found = session.scalar(
            select(PlacePhoto).where(PlacePhoto.place_id == place.id, PlacePhoto.original_url == original)
        )
        if found is not None:
            return found
    if thumb:
        found = session.scalar(
            select(PlacePhoto).where(PlacePhoto.place_id == place.id, PlacePhoto.thumbnail_url == thumb)
        )
        if found is not None:
            return found
    filename = _photo_filename_hint(image)
    if not filename:
        return None
    photos = list(session.scalars(select(PlacePhoto).where(PlacePhoto.place_id == place.id)).all())
    for photo in photos:
        blob = f"{photo.original_url or ''} {photo.thumbnail_url or ''} {photo.source_url or ''}"
        if filename in blob.replace(" ", "_"):
            return photo
    return None


def _apply_photo(session: Session, place: Place, record: CanonicalRecord) -> bool:
    image = record.image
    if not image:
        return False
    original = image.get("original_url") or image.get("source_url")
    thumb = image.get("thumbnail_url")
    if not original and not thumb:
        return False
    existing = _find_existing_photo(session, place, image)
    if existing is not None:
        changed = False
        updates = {
            "source_url": image.get("source_url") or record.source_url,
            "original_url": original,
            "thumbnail_url": thumb,
            "author": image.get("author"),
            "license": image.get("license"),
            "license_url": image.get("license_url"),
            "attribution": image.get("attribution"),
        }
        for attr, value in updates.items():
            if value and getattr(existing, attr) != value:
                setattr(existing, attr, value)
                changed = True
        return changed
    has_primary = session.scalar(
        select(PlacePhoto.id).where(PlacePhoto.place_id == place.id, PlacePhoto.is_primary == 1)
    )
    photo = PlacePhoto(
        place_id=place.id,
        source=str(image.get("source") or "wikimedia_commons"),
        source_url=image.get("source_url") or record.source_url,
        original_url=original,
        thumbnail_url=thumb,
        author=image.get("author"),
        license=image.get("license"),
        license_url=image.get("license_url"),
        attribution=image.get("attribution"),
        is_primary=0 if has_primary else 1,
        created_at=now_iso(),
    )
    session.add(photo)
    return True


def _incoming_master_fields(record: CanonicalRecord) -> dict[str, Any]:
    data: dict[str, Any] = {}
    if record.name:
        data["name"] = record.name
    if record.alternative_names:
        data["alternative_names"] = list(record.alternative_names)
    if record.types:
        data["types"] = list(record.types)
    for field_name in (
        "condition",
        "visitability",
        "latitude",
        "longitude",
        "address",
        "municipality",
        "district",
        "region",
        "short_description",
        "official_website",
        "wikipedia_url",
        "heritage_status",
        "municipality_code",
        "district_code",
        "region_code",
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
        "unesco",
    ):
        value = record_field_value(record, field_name)
        if value is None or value == "":
            continue
        if field_name == "amenities" and not value:
            continue
        data[field_name] = value
    return data


def _write_master_field(
    session: Session,
    place: Place,
    field_name: str,
    incoming: Any,
    record: CanonicalRecord,
    run: ImportRun,
    old_source_value: Any,
) -> bool:
    current = master_value(place, field_name)
    if has_override(session, place.id, field_name):
        if not values_equal(current, incoming):
            existing_change = session.scalar(
                select(ImportFieldChange).where(
                    ImportFieldChange.place_id == place.id,
                    ImportFieldChange.field_name == field_name,
                    ImportFieldChange.status == "open",
                )
            )
            encoded_old = encode_value(old_source_value) if old_source_value is not None else None
            encoded_new = encode_value(incoming)
            encoded_master = encode_value(current)
            if existing_change is None:
                session.add(
                    ImportFieldChange(
                        import_run_id=run.id,
                        place_id=place.id,
                        field_name=field_name,
                        old_source_value=encoded_old,
                        new_source_value=encoded_new,
                        master_value=encoded_master,
                        status="open",
                    )
                )
            else:
                existing_change.import_run_id = run.id
                existing_change.old_source_value = encoded_old
                existing_change.new_source_value = encoded_new
                existing_change.master_value = encoded_master
        return False
    if not source_may_write_master(session, place, field_name, record.source_type):
        return False
    if field_name == "alternative_names":
        merged = _merge_alt_names(place, incoming if isinstance(incoming, list) else [])
        if values_equal(place.alt_names, merged):
            return False
        place.alternative_names = encode_value(merged)
        return True
    if field_name == "types":
        incoming_codes = [str(code) for code in incoming]
        current_codes = [item.code for item in place.types]
        merged_codes = list(dict.fromkeys([*current_codes, *incoming_codes]))
        if merged_codes == current_codes:
            return False
        place.types = _types_for_codes(session, merged_codes)
        return True
    if values_equal(current, incoming):
        return False
    apply_value_to_place(place, field_name, incoming, session)
    return True


def _apply_master_from_record(
    session: Session,
    place: Place,
    record: CanonicalRecord,
    run: ImportRun,
    *,
    creating: bool,
    old_source_values: dict[str, Any] | None = None,
) -> bool:
    changed = False
    incoming_fields = _incoming_master_fields(record)
    for field_name, incoming in incoming_fields.items():
        old_source = (old_source_values or {}).get(field_name)
        if creating:
            if field_name == "types":
                place.types = _types_for_codes(session, list(incoming))
            elif field_name in {"alternative_names", "amenities"}:
                place_field = "alternative_names" if field_name == "alternative_names" else "amenities"
                setattr(place, place_field, encode_value(list(incoming)))
            else:
                apply_value_to_place(place, field_name, incoming, session)
            changed = True
        elif _write_master_field(session, place, field_name, incoming, record, run, old_source):
            changed = True
    if creating:
        if place.latitude is None or place.longitude is None:
            place.quality_status = "NEEDS_REVIEW"
        else:
            place.quality_status = "PROBABLE"
    return changed


def create_place_from_record(session: Session, record: CanonicalRecord, run: ImportRun) -> Place:
    now = record.fetched_at or now_iso()
    place = Place(
        name=record.name.strip(),
        created_at=now,
        updated_at=now,
        quality_status="NEEDS_REVIEW",
    )
    session.add(place)
    session.flush()
    _apply_master_from_record(session, place, record, run, creating=True)
    _attach_identities(session, place, record)
    _apply_photo(session, place, record)
    place.updated_at = now_iso()
    session.flush()
    return place


def update_place_from_record(session: Session, place: Place, record: CanonicalRecord, run: ImportRun) -> bool:
    public_id = place.public_id
    old_source_values: dict[str, Any] = {}
    primary = _lookup_source(
        session, record.source_type, record.external_id, place_id=place.id
    )
    if primary is not None:
        for field_name in SOURCE_VALUE_FIELDS:
            old_source_values[field_name] = _old_source_value(session, primary, field_name)
    identities_changed = _attach_identities(session, place, record)
    master_changed = _apply_master_from_record(
        session, place, record, run, creating=False, old_source_values=old_source_values
    )
    photo_changed = _apply_photo(session, place, record)
    if place.public_id != public_id:
        raise ValueError("Place.public_id is immutable and must never be changed")
    changed = identities_changed or master_changed or photo_changed
    if changed:
        place.updated_at = now_iso()
    session.flush()
    return changed


def _open_review_for(session: Session, record: CanonicalRecord) -> ImportReview | None:
    if not record.external_id:
        return None
    return session.scalar(
        select(ImportReview).where(
            ImportReview.source_type == record.source_type,
            ImportReview.external_id == record.external_id,
            ImportReview.status == "open",
        )
    )


def enqueue_review(session: Session, run: ImportRun, record: CanonicalRecord, decision: MatchDecision) -> ImportReview:
    existing = _open_review_for(session, record)
    best = decision.candidates[0] if decision.candidates else None
    payload = json.dumps(record.to_dict(), ensure_ascii=False, default=str)
    if existing is not None:
        existing.import_run_id = run.id
        existing.raw_data = payload
        existing.match_reason = decision.reason
        existing.match_score = best.score if best else None
        existing.candidate_place_id = best.place.id if best else None
        for old in list(existing.candidates):
            session.delete(old)
        session.flush()
        review = existing
    else:
        review = ImportReview(
            import_run_id=run.id,
            source_type=record.source_type,
            external_id=record.external_id,
            candidate_place_id=best.place.id if best else None,
            match_score=best.score if best else None,
            match_reason=decision.reason,
            raw_data=payload,
            status="open",
        )
        session.add(review)
        session.flush()
    for candidate in decision.candidates:
        session.add(
            ImportReviewCandidate(
                import_review_id=review.id,
                place_id=candidate.place.id,
                score=candidate.score,
                reason=candidate.reason,
            )
        )
    session.flush()
    return review


def _outcome(record: CanonicalRecord, decision: MatchDecision, public_id: str | None = None) -> RecordOutcome:
    return RecordOutcome(
        name=record.name,
        level=decision.level,
        action=decision.action,
        reason=decision.reason,
        public_id=public_id,
        candidate_names=[c.place.name for c in decision.candidates],
    )


def _apply_one(
    session: Session,
    run: ImportRun,
    record: CanonicalRecord,
    log_lines: list[str],
    match_index: MatchIndex,
) -> RecordOutcome:
    decision = match_record(session, record, index=match_index)
    if decision.level == LEVEL_FAILED:
        run.records_failed += 1
        log_lines.append(f"FAIL {record.name}: {decision.reason}")
        return _outcome(record, decision)
    if decision.level == LEVEL_IGNORED:
        run.records_ignored += 1
        log_lines.append(f"IGNORE {record.source_type}/{record.external_id}")
        return _outcome(record, decision)
    if decision.action == "review":
        enqueue_review(session, run, record, decision)
        run.records_review += 1
        log_lines.append(f"REVIEW {record.name}: {decision.reason}")
        return _outcome(record, decision, decision.candidates[0].place.public_id if decision.candidates else None)
    if decision.action == "create":
        place = create_place_from_record(session, record, run)
        match_index.register(place)
        run.records_created += 1
        log_lines.append(f"CREATE {place.name} public_id={place.public_id}")
        return _outcome(record, decision, place.public_id)
    if decision.action == "update" and decision.place is not None:
        place = decision.place
        changed = update_place_from_record(session, place, record, run)
        match_index.register(place)
        if decision.level == LEVEL_B:
            log_lines.append(f"{LEVEL_B} {record.name} -> {place.public_id} {decision.reason}")
        if changed:
            run.records_updated += 1
            log_lines.append(f"UPDATE {place.name} public_id={place.public_id} {decision.reason}")
        else:
            run.records_unchanged += 1
            log_lines.append(f"UNCHANGED {place.name} public_id={place.public_id}")
        return _outcome(record, decision, place.public_id)
    run.records_failed += 1
    log_lines.append(f"FAIL {record.name}: neočekávaná akce {decision.action}")
    return _outcome(record, decision)


def _new_run(source_type: str, status: str, backup_path: str | None, received: int) -> ImportRun:
    return ImportRun(
        source_type=source_type,
        started_at=now_iso(),
        records_received=received,
        status=status,
        backup_path=backup_path,
    )


def _fill_result(run: ImportRun, outcomes: list[RecordOutcome], error: str | None = None) -> ImportResult:
    return ImportResult(
        run_id=run.id,
        status=run.status,
        source_type=run.source_type,
        backup_path=run.backup_path,
        records_received=run.records_received,
        records_created=run.records_created,
        records_updated=run.records_updated,
        records_unchanged=run.records_unchanged,
        records_review=run.records_review,
        records_failed=run.records_failed,
        records_ignored=run.records_ignored,
        log=run.log or "",
        outcomes=outcomes,
        error=error,
    )


def _report(
    session: Session,
    *,
    status: str,
    phase: str,
    source_type: str,
    current: int,
    total: int,
    created: int = 0,
    updated: int = 0,
    unchanged: int = 0,
    review: int = 0,
    failed: int = 0,
    ignored: int = 0,
    current_name: str = "",
    message: str = "",
    force: bool = False,
    kind: str | None = None,
    run_id: int | None = None,
) -> None:
    payload: dict[str, object] = {
        "status": status,
        "phase": phase,
        "source_type": source_type,
        "current": current,
        "total": total,
        "created": created,
        "updated": updated,
        "unchanged": unchanged,
        "review": review,
        "failed": failed,
        "ignored": ignored,
        "current_name": current_name,
        "message": message,
        "force": force,
    }
    if kind is not None:
        payload["kind"] = kind
    if run_id is not None:
        payload["run_id"] = run_id
    write_progress(data_dir=data_dir_for_session(session), **payload)


def preview_import(
    session: Session,
    records: Iterable[CanonicalRecord],
    source_type: str,
    extra_log: str | None = None,
) -> ImportResult:
    """Dry-run: matching bez zápisu Place. Uloží ImportRun se status=preview."""
    items = list(records)
    log_lines: list[str] = []
    if extra_log:
        log_lines.append(extra_log)
    outcomes: list[RecordOutcome] = []
    created = updated = unchanged = review = failed = ignored = 0
    total = len(items)
    _report(
        session,
        status="running",
        phase="match",
        source_type=source_type,
        current=0,
        total=total,
        message=f"Náhled 0 / {total}",
        force=True,
        kind="preview",
    )
    match_index = MatchIndex.build(session)
    for index, record in enumerate(items, start=1):
        decision = match_record(session, record, index=match_index)
        public_id = decision.place.public_id if decision.place else (
            decision.candidates[0].place.public_id if decision.candidates else None
        )
        outcomes.append(_outcome(record, decision, public_id))
        if decision.level == LEVEL_FAILED:
            failed += 1
        elif decision.level == LEVEL_IGNORED:
            ignored += 1
        elif decision.action == "review":
            review += 1
        elif decision.action == "create":
            created += 1
        elif decision.action == "update":
            updated += 1  # preview nerozliší unchanged
        log_lines.append(f"PREVIEW {decision.level} {record.name}: {decision.reason}")
        _report(
            session,
            status="running",
            phase="match",
            source_type=source_type,
            current=index,
            total=total,
            created=created,
            updated=updated,
            unchanged=unchanged,
            review=review,
            failed=failed,
            ignored=ignored,
            current_name=record.name,
            message=f"Náhled {index} / {total}",
            force=index == total,
        )

    run = _new_run(source_type, "preview", None, len(items))
    run.records_created = created
    run.records_updated = updated
    run.records_unchanged = unchanged
    run.records_review = review
    run.records_failed = failed
    run.records_ignored = ignored
    run.finished_at = now_iso()
    run.log = "\n".join(log_lines)
    session.add(run)
    session.commit()
    session.refresh(run)
    _report(
        session,
        status="preview",
        phase="done",
        source_type=source_type,
        current=total,
        total=total,
        created=created,
        updated=updated,
        unchanged=unchanged,
        review=review,
        failed=failed,
        ignored=ignored,
        message=f"Náhled hotový: {total} / {total}",
        force=True,
        kind="preview",
        run_id=run.id,
    )
    return _fill_result(run, outcomes)


def apply_import(
    session: Session,
    records: Iterable[CanonicalRecord],
    source_type: str,
    *,
    make_backup: bool = True,
    extra_log: str | None = None,
) -> ImportResult:
    items = list(records)
    total = len(items)
    _report(
        session,
        status="running",
        phase="backup" if make_backup else "write",
        source_type=source_type,
        current=0,
        total=total,
        message="Vytvářím zálohu…" if make_backup else f"Zapisuji 0 / {total}",
        force=True,
        kind="apply",
    )
    backup_path: Path | None = None
    if make_backup:
        backup_path = backup_before_import(session, source_type)

    started = now_iso()
    backup_str = str(backup_path) if backup_path else None
    log_lines: list[str] = []
    if extra_log:
        log_lines.append(extra_log)
    outcomes: list[RecordOutcome] = []
    run = _new_run(source_type, "running", backup_str, total)
    run.started_at = started
    session.add(run)
    session.flush()
    _report(
        session,
        status="running",
        phase="write",
        source_type=source_type,
        current=0,
        total=total,
        message=f"Zapisuji 0 / {total}",
        force=True,
    )

    match_index = MatchIndex.build(session)
    try:
        for index, record in enumerate(items, start=1):
            if not record.fetched_at:
                record.fetched_at = now_iso()
            outcomes.append(_apply_one(session, run, record, log_lines, match_index))
            _report(
                session,
                status="running",
                phase="write",
                source_type=source_type,
                current=index,
                total=total,
                created=run.records_created,
                updated=run.records_updated,
                unchanged=run.records_unchanged,
                review=run.records_review,
                failed=run.records_failed,
                ignored=run.records_ignored,
                current_name=record.name,
                message=f"Zapisuji {index} / {total}",
                force=index == total,
            )
        run.status = "applied"
        run.finished_at = now_iso()
        run.log = "\n".join(log_lines)
        session.commit()
        session.refresh(run)
        _log.info(
            "import applied source=%s received=%s created=%s updated=%s unchanged=%s review=%s ignored=%s failed=%s",
            source_type,
            run.records_received,
            run.records_created,
            run.records_updated,
            run.records_unchanged,
            run.records_review,
            run.records_ignored,
            run.records_failed,
        )
        _report(
            session,
            status="applied",
            phase="done",
            source_type=source_type,
            current=total,
            total=total,
            created=run.records_created,
            updated=run.records_updated,
            unchanged=run.records_unchanged,
            review=run.records_review,
            failed=run.records_failed,
            ignored=run.records_ignored,
            message=f"Import zapsán: {total} / {total}",
            force=True,
            kind="apply",
            run_id=run.id,
        )
        return _fill_result(run, outcomes)
    except Exception as exc:
        session.rollback()
        fail_run = _new_run(source_type, "rolled_back", backup_str, len(items))
        fail_run.started_at = started
        fail_run.finished_at = now_iso()
        fail_run.records_failed = len(items)
        fail_run.log = f"ROLLBACK: {exc}\n" + "\n".join(log_lines)
        session.add(fail_run)
        session.commit()
        session.refresh(fail_run)
        _log.exception("import rolled back source=%s", source_type)
        _report(
            session,
            status="rolled_back",
            phase="error",
            source_type=source_type,
            current=len(outcomes),
            total=total,
            failed=len(items),
            message="Import selhal a byl vrácen zpět.",
            force=True,
        )
        result = _fill_result(fail_run, outcomes, error=str(exc))
        result.status = "rolled_back"
        raise ImportApplyError(str(exc), result) from exc


def existing_external_ids(session: Session, source_type: str) -> set[str]:
    rows = session.scalars(
        select(PlaceSource.external_id).where(
            PlaceSource.source_type == source_type,
            PlaceSource.external_id.is_not(None),
            PlaceSource.external_id != "",
        )
    )
    return {str(item) for item in rows if item}


class ImportApplyError(RuntimeError):
    def __init__(self, message: str, result: ImportResult):
        super().__init__(message)
        self.result = result


def reprocess_open_reviews(session: Session, *, make_backup: bool = True) -> ImportResult:
    """Znovu spáruje otevřenou frontu po změně pravidel (bez C4 jen podle názvu)."""
    reviews = list(
        session.scalars(
            select(ImportReview).where(ImportReview.status == "open").order_by(ImportReview.id)
        ).all()
    )
    total = len(reviews)
    _report(
        session,
        status="running",
        phase="backup" if make_backup else "write",
        source_type="review_reprocess",
        current=0,
        total=total,
        message="Vytvářím zálohu…" if make_backup else f"Zapisuji 0 / {total}",
        force=True,
        kind="apply",
    )
    backup_path = backup_before_import(session, "review_reprocess") if make_backup else None
    started = now_iso()
    log_lines = ["Reprocess open reviews with current A/B/C rules."]
    outcomes: list[RecordOutcome] = []
    run = _new_run("review_reprocess", "running", str(backup_path) if backup_path else None, total)
    run.started_at = started
    session.add(run)
    session.flush()
    match_index = MatchIndex.build(session)
    try:
        for index, review in enumerate(reviews, start=1):
            record = review_record(review)
            decision = match_record(session, record, index=match_index)
            public_id: str | None = None
            if decision.level == LEVEL_IGNORED:
                review.status = "ignored"
                review.resolution = decision.reason
                review.resolved_at = now_iso()
                review.import_run_id = run.id
                run.records_ignored += 1
            elif decision.action == "review":
                enqueue_review(session, run, record, decision)
                run.records_review += 1
                if decision.candidates:
                    public_id = decision.candidates[0].place.public_id
            elif decision.action == "create":
                place = create_place_from_record(session, record, run)
                match_index.register(place)
                review.status = "created_new"
                review.resolution = f"Vytvořeno nové public_id={place.public_id}"
                review.resolved_at = now_iso()
                review.import_run_id = run.id
                run.records_created += 1
                public_id = place.public_id
                log_lines.append(f"CREATE {place.name} public_id={place.public_id}")
            elif decision.action == "update" and decision.place is not None:
                place = decision.place
                changed = update_place_from_record(session, place, record, run)
                match_index.register(place)
                review.status = "merged"
                review.candidate_place_id = place.id
                review.resolution = f"Sloučeno do {place.public_id}"
                review.resolved_at = now_iso()
                review.import_run_id = run.id
                public_id = place.public_id
                if changed:
                    run.records_updated += 1
                    log_lines.append(f"MERGE {record.name} -> {place.public_id}")
                else:
                    run.records_unchanged += 1
            else:
                review.status = "ignored"
                review.resolution = decision.reason
                review.resolved_at = now_iso()
                review.import_run_id = run.id
                run.records_failed += 1
            outcomes.append(_outcome(record, decision, public_id))
            _report(
                session,
                status="running",
                phase="write",
                source_type="review_reprocess",
                current=index,
                total=total,
                created=run.records_created,
                updated=run.records_updated,
                unchanged=run.records_unchanged,
                review=run.records_review,
                failed=run.records_failed,
                ignored=run.records_ignored,
                current_name=record.name,
                message=f"Zapisuji {index} / {total}",
                force=index == total,
            )
        run.status = "applied"
        run.finished_at = now_iso()
        run.log = "\n".join(log_lines)
        session.commit()
        session.refresh(run)
        _report(
            session,
            status="applied",
            phase="done",
            source_type="review_reprocess",
            current=total,
            total=total,
            created=run.records_created,
            updated=run.records_updated,
            unchanged=run.records_unchanged,
            review=run.records_review,
            failed=run.records_failed,
            ignored=run.records_ignored,
            message=f"Fronta přepočtena: {total} / {total}",
            force=True,
            kind="apply",
            run_id=run.id,
        )
        return _fill_result(run, outcomes)
    except Exception as exc:
        session.rollback()
        fail_run = _new_run("review_reprocess", "rolled_back", str(backup_path) if backup_path else None, total)
        fail_run.started_at = started
        fail_run.finished_at = now_iso()
        fail_run.records_failed = total
        fail_run.log = f"ROLLBACK: {exc}\n" + "\n".join(log_lines)
        session.add(fail_run)
        session.commit()
        _report(
            session,
            status="rolled_back",
            phase="error",
            source_type="review_reprocess",
            current=0,
            total=total,
            failed=total,
            message="Přepočet fronty selhal a byl vrácen zpět.",
            force=True,
        )
        raise ImportApplyError(str(exc), _fill_result(fail_run, outcomes, error=str(exc))) from exc


def record_failed_run(session: Session, source_type: str, error: str, received: int = 0) -> ImportRun:
    run = _new_run(source_type, "failed", None, received)
    run.finished_at = now_iso()
    run.records_failed = received
    run.log = f"FAILED: {error}"
    session.add(run)
    session.commit()
    session.refresh(run)
    _log.error("import failed source=%s error=%s", source_type, error)
    return run


def review_record(review: ImportReview) -> CanonicalRecord:
    data = json.loads(review.raw_data)
    return CanonicalRecord.from_dict(data)


def resolve_merge(session: Session, review: ImportReview, place: Place) -> Place:
    if review.status != "open":
        raise ValueError("Review už je vyřízená")
    record = review_record(review)
    run = review.import_run
    public_id = place.public_id
    update_place_from_record(session, place, record, run)
    if place.public_id != public_id:
        raise ValueError("Place.public_id is immutable and must never be changed")
    review.status = "merged"
    review.candidate_place_id = place.id
    review.resolution = f"Sloučeno do {place.public_id}"
    review.resolved_at = now_iso()
    session.commit()
    session.refresh(place)
    _log.info("review merged id=%s into public_id=%s", review.id, place.public_id)
    return place


def resolve_create_new(session: Session, review: ImportReview) -> Place:
    if review.status != "open":
        raise ValueError("Review už je vyřízená")
    record = review_record(review)
    place = create_place_from_record(session, record, review.import_run)
    review.status = "created_new"
    review.resolution = f"Vytvořeno nové public_id={place.public_id}"
    review.resolved_at = now_iso()
    session.commit()
    session.refresh(place)
    _log.info("review created_new id=%s public_id=%s", review.id, place.public_id)
    return place


def resolve_ignore(session: Session, review: ImportReview) -> ImportReview:
    if review.status != "open":
        raise ValueError("Review už je vyřízená")
    review.status = "ignored"
    review.resolution = "Ignorováno"
    review.resolved_at = now_iso()
    session.commit()
    _log.info("review ignored id=%s %s/%s", review.id, review.source_type, review.external_id)
    return review


def unignore_review(session: Session, review: ImportReview) -> ImportReview:
    if review.status != "ignored":
        raise ValueError("Položka není ignorovaná")
    review.status = "open"
    review.resolution = None
    review.resolved_at = None
    session.commit()
    return review
