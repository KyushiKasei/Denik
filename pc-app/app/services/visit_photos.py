"""Osobní fotky u návštěv — soubory vedle SQLite, ne v catalog.json."""

from __future__ import annotations

import re
from pathlib import Path

from app.config import get_visit_photos_dir

_SAFE = re.compile(r"[^0-9A-Za-z._-]+")
_VISIT_DIR = re.compile(r"^[0-9a-fA-F-]{36}$")
MAX_PHOTOS_PER_VISIT = 3
MAX_PHOTO_BYTES = 8 * 1024 * 1024


def is_visit_id(value: str) -> bool:
    return bool(_VISIT_DIR.match(value))


def visit_photo_dir(visit_public_id: str) -> Path:
    if not is_visit_id(visit_public_id):
        raise ValueError("Neplatné ID návštěvy")
    folder = get_visit_photos_dir() / visit_public_id
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def list_visit_photos(visit_public_id: str) -> list[Path]:
    if not is_visit_id(visit_public_id):
        return []
    folder = get_visit_photos_dir() / visit_public_id
    if not folder.is_dir():
        return []
    return sorted(path for path in folder.iterdir() if path.is_file())


def save_visit_photo(visit_public_id: str, filename: str, data: bytes) -> Path:
    if len(data) > MAX_PHOTO_BYTES:
        raise ValueError("Fotka je větší než 8 MB.")
    name = Path(filename.replace("\\", "/")).name
    name = _SAFE.sub("", name) or "photo.jpg"
    if not name.lower().endswith((".jpg", ".jpeg", ".png", ".webp")):
        name = f"{name}.jpg"
    target = visit_photo_dir(visit_public_id) / name
    if not target.exists() and len(list_visit_photos(visit_public_id)) >= MAX_PHOTOS_PER_VISIT:
        raise ValueError(f"U návštěvy můžou být nejvýš {MAX_PHOTOS_PER_VISIT} fotky.")
    target.write_bytes(data)
    return target


def iter_visit_photo_files() -> list[tuple[str, Path]]:
    root = get_visit_photos_dir()
    if not root.is_dir():
        return []
    rows: list[tuple[str, Path]] = []
    for folder in sorted(root.iterdir()):
        if not folder.is_dir() or not _VISIT_DIR.match(folder.name):
            continue
        for path in sorted(folder.iterdir()):
            if path.is_file():
                rows.append((folder.name, path))
    return rows


def photos_for_visits(visit_ids: list[str]) -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for visit_id in visit_ids:
        if not is_visit_id(visit_id):
            continue
        names = [path.name for path in list_visit_photos(visit_id)]
        if names:
            result[visit_id] = names
    return result
