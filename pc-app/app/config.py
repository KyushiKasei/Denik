"""Cesty k datům. Živá SQLite nesmí ležet v Dropbox/OneDrive sync."""

from __future__ import annotations

import os
from pathlib import Path


APP_NAME = "PamatkyDenik"
DEFAULT_PORT = 8765

_PACKAGE_DIR = Path(__file__).resolve().parent
PC_APP_DIR = _PACKAGE_DIR.parent
REPO_ROOT = PC_APP_DIR.parent


def get_data_dir() -> Path:
    """Složka s pamatky.sqlite3 a zálohami.

    PAMATKY_DATA_DIR — explicitní cesta (testy, přenositelná instalace).
    PAMATKY_PORTABLE=1 — ./data vedle kořene projektu / instalace.
    jinak — %LOCALAPPDATA%\\PamatkyDenik, aby vývoj v Dropboxu neničil DB.
    """
    override = os.environ.get("PAMATKY_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if os.environ.get("PAMATKY_PORTABLE") == "1":
        return (REPO_ROOT / "data").resolve()
    local_app = os.environ.get("LOCALAPPDATA")
    base = Path(local_app) if local_app else Path.home() / "AppData" / "Local"
    return (base / APP_NAME).resolve()


def get_database_path() -> Path:
    return get_data_dir() / "pamatky.sqlite3"


def sqlite_url(path: Path | None = None) -> str:
    db_path = (path or get_database_path()).resolve()
    return "sqlite:///" + db_path.as_posix()


def get_database_url() -> str:
    return sqlite_url()


def get_export_dir() -> Path:
    return get_data_dir() / "export"


def get_default_catalog_path() -> Path:
    return get_export_dir() / "catalog.json"


def get_default_diary_path() -> Path:
    return get_export_dir() / "diary.json"


def catalog_schema_path() -> Path:
    return REPO_ROOT / "shared" / "schemas" / "catalog.schema.json"


def diary_schema_path() -> Path:
    return REPO_ROOT / "shared" / "schemas" / "diary.schema.json"


def ensure_data_dir() -> Path:
    data_dir = get_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    (data_dir / "backups").mkdir(exist_ok=True)
    (data_dir / "logs").mkdir(exist_ok=True)
    get_export_dir().mkdir(exist_ok=True)
    return data_dir
