"""Rozbalení a sbalení diary.json nebo ZIP s fotkami."""

from __future__ import annotations

import json
import re
from io import BytesIO
from pathlib import Path
from typing import Any
from zipfile import ZIP_STORED, BadZipFile, ZipFile

from app.ids import new_public_id
from app.services.diary_schema import MAX_DIARY_JSON_BYTES, validate_diary
from app.services.visit_photos import (
    MAX_PHOTO_BYTES,
    MAX_PHOTOS_PER_VISIT,
    iter_visit_photo_files,
    list_visit_photos,
    save_visit_photo,
)

MAX_UPLOAD_BYTES = 80 * 1024 * 1024

_PHOTO = re.compile(
    r"^photos/([0-9a-fA-F-]{36})/([0-9a-fA-F-]{36})\.(jpe?g|png|webp)$",
    re.IGNORECASE,
)
_UUID = re.compile(r"^[0-9a-fA-F-]{36}$")
_PHOTO_EXT = {"jpg", "jpeg", "png", "webp"}


def photo_zip_arcname(visit_id: str, path: Path) -> str:
    ext = path.suffix.lower().lstrip(".")
    if ext == "jpeg":
        ext = "jpg"
    if ext not in {"jpg", "png", "webp"}:
        ext = "jpg"
    stem = path.stem
    photo_id = stem if _UUID.match(stem) else new_public_id()
    return f"photos/{visit_id}/{photo_id}.{ext}"


def build_diary_zip(diary: dict[str, Any]) -> bytes:
    buffer = BytesIO()
    # PWA readZip umí jen STORE (bez komprese), stejně jako vlastní export z telefonu.
    with ZipFile(buffer, "w", compression=ZIP_STORED) as archive:
        archive.writestr("diary.json", json.dumps(diary, ensure_ascii=False, indent=2) + "\n")
        for visit_id, path in iter_visit_photo_files():
            if path.suffix.lower().lstrip(".") not in _PHOTO_EXT:
                continue
            try:
                size = path.stat().st_size
            except OSError:
                continue
            if size > MAX_PHOTO_BYTES:
                continue
            archive.writestr(photo_zip_arcname(visit_id, path), path.read_bytes())
    return buffer.getvalue()


def parse_diary_upload(raw: bytes, filename: str | None) -> tuple[dict[str, Any], int]:
    if len(raw) > MAX_UPLOAD_BYTES:
        raise ValueError("Soubor je větší než 80 MB.")
    name = (filename or "").lower()
    if name.endswith(".zip") or raw[:2] == b"PK":
        return _from_zip(raw)
    if len(raw) > MAX_DIARY_JSON_BYTES:
        raise ValueError("diary.json je moc velký.")
    data = json.loads(raw.decode("utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Soubor není objekt JSON.")
    return data, 0


def _from_zip(raw: bytes) -> tuple[dict[str, Any], int]:
    try:
        archive = ZipFile(BytesIO(raw))
    except BadZipFile as exc:
        raise ValueError("Soubor ZIP není platný.") from exc
    with archive:
        diary_name = None
        for item in archive.namelist():
            if item.replace("\\", "/").rstrip("/").split("/")[-1] == "diary.json":
                diary_name = item
                break
        if diary_name is None:
            raise ValueError("V ZIP chybí diary.json.")
        _require_stored(archive, diary_name)
        diary_info = archive.getinfo(diary_name)
        if diary_info.file_size > MAX_DIARY_JSON_BYTES:
            raise ValueError("diary.json v ZIP je moc velký.")
        data = json.loads(archive.read(diary_name).decode("utf-8"))
        if not isinstance(data, dict):
            raise ValueError("diary.json v ZIP není objekt.")
        # PWA validuje deník před zápisem fotek. Bez toho neplatný ZIP nechá osiřelé soubory.
        validate_diary(data)
        photos = 0
        for item in archive.namelist():
            path = item.replace("\\", "/")
            match = _PHOTO.match(path)
            if not match:
                continue
            _require_stored(archive, item)
            info = archive.getinfo(item)
            if info.file_size > MAX_PHOTO_BYTES:
                continue
            visit_id = match.group(1)
            filename = f"{match.group(2)}.{match.group(3).lower()}"
            existing = [row.name for row in list_visit_photos(visit_id)]
            if filename not in existing and len(existing) >= MAX_PHOTOS_PER_VISIT:
                continue
            save_visit_photo(visit_id, filename, archive.read(item))
            photos += 1
        return data, photos


def _require_stored(archive: ZipFile, name: str) -> None:
    info = archive.getinfo(name)
    if info.compress_type != ZIP_STORED:
        raise ValueError("ZIP musí být bez komprese (store), jako export z této aplikace.")
