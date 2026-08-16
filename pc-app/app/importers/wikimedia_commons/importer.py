"""Doplnění licence a atribuce k P18 fotkám. Binární soubory se nestahují."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import REPO_ROOT, get_data_dir
from app.db.models import Place, PlacePhoto, now_iso
from app.importers.base import CanonicalRecord
from app.importers.wikimedia_commons.client import CommonsClient
from app.importers.wikimedia_commons.parser import commons_filename, records_from_imageinfo
from app.logging_setup import get_logger

SOURCE_TYPE = "wikimedia_commons"
SAMPLE_JSON = REPO_ROOT / "fixtures" / "import" / "wikimedia_commons" / "imageinfo.json"
_log = get_logger()


def cache_path() -> Path:
    return get_data_dir() / "cache" / "commons_last.json"


def _attachments_from_places(places: list[Place]) -> list[dict]:
    attachments: list[dict] = []
    for place in places:
        if place.archived_at:
            continue
        ids = {source.source_type: source.external_id for source in place.sources if source.external_id}
        seen: set[str] = set()
        for photo in place.photos:
            filename = commons_filename(photo.original_url) or commons_filename(photo.thumbnail_url) or commons_filename(photo.source_url)
            if not filename or filename.casefold() in seen:
                continue
            seen.add(filename.casefold())
            attachments.append(
                {
                    "filename": filename,
                    "name": place.name,
                    "external_ids": ids,
                    "types": [item.code for item in place.types],
                    "latitude": place.latitude,
                    "longitude": place.longitude,
                    "municipality": place.municipality,
                }
            )
    return attachments


def records_from_sample(path: Path | None = None, fetched_at: str | None = None) -> list[CanonicalRecord]:
    data = json.loads((path or SAMPLE_JSON).read_text(encoding="utf-8"))
    attachments = data.get("attachments") or []
    payload = data.get("imageinfo") or data
    return records_from_imageinfo(payload, attachments, fetched_at or now_iso())


def fetch_commons_records(session: Session, *, use_cache: bool = False, client: CommonsClient | None = None) -> list[CanonicalRecord]:
    places = list(session.scalars(select(Place).where(Place.archived_at.is_(None))).all())
    attachments = _attachments_from_places(places)
    if not attachments:
        return []
    filenames = [str(item["filename"]) for item in attachments]
    payload = None
    if use_cache:
        path = cache_path()
        if path.is_file():
            payload = json.loads(path.read_text(encoding="utf-8"))
    if payload is None:
        client = client or CommonsClient()
        payload = client.fetch_imageinfo(filenames)
        cache = cache_path()
        cache.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    records = records_from_imageinfo(payload, attachments, now_iso())
    _log.info("commons records=%s", len(records))
    return records
