"""Výměnná složka s telefonem: lidský Dropbox/USB, ne API a ne živá SQLite."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_data_dir
from app.logging_setup import get_logger
from app.services.catalog_export import export_catalog
from app.services.diary_bundle import MAX_UPLOAD_BYTES, parse_diary_upload
from app.services.diary_io import DiaryImportResult, export_diary_zip, import_diary

INCOMING_DIARY_NAMES = ("diary.zip", "diary.json")
OUTGOING_DIARY_NAME = "diary-z-pc.zip"
OUTGOING_CATALOG_NAME = "catalog.json"
CONFIG_NAME = "exchange.json"

_log = get_logger()


class ExchangeError(ValueError):
    """Neplatná cesta nebo ve složce nic ke sloučení."""


@dataclass(frozen=True)
class ExchangeStatus:
    folder: Path | None
    folder_exists: bool
    incoming: Path | None
    outgoing_diary: Path | None
    outgoing_catalog: Path | None
    in_data_dir: bool


def exchange_config_path() -> Path:
    return get_data_dir() / CONFIG_NAME


def load_exchange_folder() -> Path | None:
    path = exchange_config_path()
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    if not isinstance(raw, dict):
        return None
    folder = str(raw.get("folder") or "").strip()
    if not folder:
        return None
    try:
        return Path(folder).expanduser().resolve()
    except OSError:
        return None


def save_exchange_folder(raw: str) -> Path:
    folder = _parse_folder(raw)
    _reject_data_dir(folder)
    folder.mkdir(parents=True, exist_ok=True)
    if not folder.is_dir():
        raise ExchangeError("Cesta ke složce není adresář.")
    config = exchange_config_path()
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(json.dumps({"folder": str(folder)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _log.info("exchange folder saved path=%s", folder)
    return folder


def find_incoming_diary(folder: Path) -> Path | None:
    candidates: list[Path] = []
    for name in INCOMING_DIARY_NAMES:
        path = folder / name
        if path.is_file() and path.name.lower() != OUTGOING_DIARY_NAME:
            candidates.append(path)
    if not candidates:
        return None
    return max(candidates, key=lambda item: item.stat().st_mtime)


def exchange_status() -> ExchangeStatus:
    folder = load_exchange_folder()
    if folder is None:
        return ExchangeStatus(
            folder=None,
            folder_exists=False,
            incoming=None,
            outgoing_diary=None,
            outgoing_catalog=None,
            in_data_dir=False,
        )
    exists = folder.is_dir()
    incoming = find_incoming_diary(folder) if exists else None
    outgoing_diary = folder / OUTGOING_DIARY_NAME
    outgoing_catalog = folder / OUTGOING_CATALOG_NAME
    return ExchangeStatus(
        folder=folder,
        folder_exists=exists,
        incoming=incoming,
        outgoing_diary=outgoing_diary if outgoing_diary.is_file() else None,
        outgoing_catalog=outgoing_catalog if outgoing_catalog.is_file() else None,
        in_data_dir=_inside_data_dir(folder),
    )


def require_exchange_folder() -> Path:
    folder = load_exchange_folder()
    if folder is None:
        raise ExchangeError("Nejdřív uložte cestu ke složce pro telefon.")
    if not folder.is_dir():
        raise ExchangeError("Složka pro telefon neexistuje. Zkontrolujte cestu.")
    _reject_data_dir(folder)
    return folder


def import_diary_from_exchange(session: Session) -> tuple[DiaryImportResult, int, Path, Path]:
    folder = require_exchange_folder()
    incoming = find_incoming_diary(folder)
    if incoming is None:
        raise ExchangeError("Ve složce není diary.zip ani diary.json z telefonu.")
    if incoming.stat().st_size > MAX_UPLOAD_BYTES:
        raise ExchangeError("Soubor je větší než 80 MB.")
    raw = incoming.read_bytes()
    data, photo_count = parse_diary_upload(raw, incoming.name)
    result = import_diary(session, data)
    outgoing = folder / OUTGOING_DIARY_NAME
    outgoing.write_bytes(export_diary_zip(session))
    _log.info("exchange diary merged from=%s to=%s", incoming, outgoing)
    return result, photo_count, incoming, outgoing


def write_catalog_to_exchange(session: Session) -> Path:
    folder = require_exchange_folder()
    destination = folder / OUTGOING_CATALOG_NAME
    export_catalog(session, destination)
    _log.info("exchange catalog written path=%s", destination)
    return destination


def open_in_os(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    try:
        if sys.platform == "win32":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.run(["open", str(path)], check=False, timeout=10)
        else:
            subprocess.run(["xdg-open", str(path)], check=False, timeout=10)
    except (OSError, subprocess.TimeoutExpired) as exc:
        _log.warning("cannot open folder path=%s error=%s", path, exc)


def _parse_folder(raw: str) -> Path:
    text = (raw or "").strip().strip('"').strip("'")
    if not text:
        raise ExchangeError("Zadejte cestu ke složce pro telefon.")
    try:
        folder = Path(text).expanduser()
        if not folder.is_absolute():
            folder = Path.cwd() / folder
        return folder.resolve()
    except OSError as exc:
        raise ExchangeError("Cesta ke složce není platná.") from exc


def _inside_data_dir(folder: Path) -> bool:
    try:
        folder.resolve().relative_to(get_data_dir().resolve())
    except ValueError:
        return False
    return True


def _reject_data_dir(folder: Path) -> None:
    if _inside_data_dir(folder):
        raise ExchangeError("Složka pro telefon nesmí ležet u živé databáze. Zvolte Dropbox nebo USB.")
