"""Záloha SQLite před rizikovým importem a ruční obnova. Posledních 20 souborů."""

from __future__ import annotations

import shutil
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from app.logging_setup import get_logger

MAX_BACKUPS = 20
SQLITE_HEADER = b"SQLite format 3\x00"
_log = get_logger()


class BackupError(Exception):
    """Neplatný soubor nebo selhání obnovy."""


@dataclass(frozen=True)
class BackupInfo:
    name: str
    path: Path
    size_bytes: int
    modified_iso: str


def session_db_path(session: Session) -> Path:
    database = session.get_bind().url.database
    if not database:
        raise RuntimeError("Session není napojená na souborovou SQLite")
    return Path(database)


def backups_dir_for(db_path: Path) -> Path:
    path = db_path.parent / "backups"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _sanitize_source(source_type: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in source_type)
    return cleaned.strip("-_") or "import"


def _unique_backup_path(folder: Path, source_type: str) -> Path:
    stamp = datetime.now().astimezone().strftime("%Y%m%d-%H%M%S")
    source = _sanitize_source(source_type)
    dest = folder / f"{stamp}-before-{source}.sqlite3"
    suffix = 2
    while dest.exists():
        dest = folder / f"{stamp}-before-{source}-{suffix}.sqlite3"
        suffix += 1
    return dest


def _copy_via_backup_api(source: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    source_conn = sqlite3.connect(str(source), timeout=10.0)
    dest_conn = sqlite3.connect(str(dest), timeout=10.0)
    try:
        source_conn.backup(dest_conn)
    finally:
        dest_conn.close()
        source_conn.close()


def backup_database_file(db_path: Path, source_type: str) -> Path:
    """Zkopíruje SQLite soubor do backups/ bez SQLAlchemy session."""
    folder = backups_dir_for(db_path)
    dest = _unique_backup_path(folder, source_type)
    _copy_via_backup_api(db_path, dest)
    prune_backups(folder)
    _log.info("backup created path=%s source=%s", dest, source_type)
    return dest


def backup_before_import(session: Session, source_type: str) -> Path:
    """Zkopíruje aktuální DB do backups/YYYYMMDD-HHMMSS-before-<source>.sqlite3."""
    db_path = session_db_path(session)
    session.flush()
    return backup_database_file(db_path, source_type)


def create_manual_backup(session: Session) -> Path:
    return backup_before_import(session, "manual")


def prune_backups(folder: Path, keep: int = MAX_BACKUPS) -> None:
    files = sorted(
        [path for path in folder.glob("*.sqlite3") if path.is_file()],
        key=lambda path: path.name,
    )
    extra = files[:-keep] if keep > 0 else files
    for path in extra:
        try:
            path.unlink()
        except OSError:
            _log.warning("cannot delete old backup %s", path)


def list_backups(db_path: Path) -> list[BackupInfo]:
    folder = backups_dir_for(db_path)
    items: list[BackupInfo] = []
    for path in folder.glob("*.sqlite3"):
        if not path.is_file():
            continue
        stat = path.stat()
        modified = datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds")
        items.append(
            BackupInfo(name=path.name, path=path, size_bytes=stat.st_size, modified_iso=modified)
        )
    items.sort(key=lambda item: item.name, reverse=True)
    return items


def resolve_backup_name(filename: str, db_path: Path) -> Path:
    name = Path(filename).name
    if name != filename or not name.endswith(".sqlite3"):
        raise BackupError("Neplatný název zálohy.")
    folder = backups_dir_for(db_path).resolve()
    path = (folder / name).resolve()
    if path.parent != folder:
        raise BackupError("Neplatný název zálohy.")
    if not path.is_file():
        raise BackupError("Záloha neexistuje.")
    return path


def is_sqlite_database(path: Path) -> bool:
    if not path.is_file() or path.stat().st_size < 100:
        return False
    with path.open("rb") as fh:
        return fh.read(16) == SQLITE_HEADER


def save_uploaded_backup(raw: bytes, db_path: Path) -> Path:
    if len(raw) < 100 or raw[:16] != SQLITE_HEADER:
        raise BackupError("Soubor není SQLite databáze.")
    folder = backups_dir_for(db_path)
    dest = _unique_backup_path(folder, "uploaded")
    dest.write_bytes(raw)
    prune_backups(folder)
    return dest


def _sidecar_paths(db_path: Path) -> tuple[Path, Path]:
    return Path(f"{db_path}-wal"), Path(f"{db_path}-shm")


def _checkpoint_and_unlock(db_path: Path) -> None:
    from app.db.session import reset_engine

    reset_engine()
    if not db_path.exists():
        return
    conn = sqlite3.connect(str(db_path), timeout=10.0)
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()


def _replace_live_db(source: Path, live: Path) -> None:
    live.parent.mkdir(parents=True, exist_ok=True)
    tmp = live.with_name(f"{live.name}.restoring")
    if tmp.exists():
        tmp.unlink()
    shutil.copy2(source, tmp)
    if live.exists():
        live.unlink()
    tmp.replace(live)
    for extra in _sidecar_paths(live):
        extra.unlink(missing_ok=True)


def restore_from_path(source: Path, live_db: Path) -> Path | None:
    """Nahradí živou SQLite souborem `source`. Vrátí cestu k bezpečnostní záloze, nebo None."""
    from app.db.migrate import run_migrations
    from app.db.seed import seed_place_types
    from app.db.session import get_engine, make_session_factory, reset_engine

    if not is_sqlite_database(source):
        raise BackupError("Soubor není SQLite databáze.")

    staging = live_db.with_name("restore-staging.sqlite3")
    if staging.exists():
        staging.unlink()
    shutil.copy2(source, staging)

    safety: Path | None = None
    try:
        _checkpoint_and_unlock(live_db)
        if live_db.exists() and live_db.resolve() != source.resolve():
            safety = backup_database_file(live_db, "restore")
        _replace_live_db(staging, live_db)
    finally:
        staging.unlink(missing_ok=True)

    reset_engine()
    try:
        run_migrations(live_db)
        engine = get_engine()
        session = make_session_factory(engine)()
        try:
            seed_place_types(session)
        finally:
            session.close()
    except Exception as exc:
        raise BackupError(f"Obnovená databáze se neotevřela: {exc}") from exc

    _log.info("database restored from=%s safety=%s", source, safety)
    return safety
