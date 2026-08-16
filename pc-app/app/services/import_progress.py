"""Průběh importu mimo SQLite transakci — UI ho čte, zatímco apply ještě necommitnul."""

from __future__ import annotations

import json
import os
import tempfile
import threading
import time
from dataclasses import asdict, dataclass, fields, is_dataclass
from pathlib import Path

from sqlalchemy.orm import Session

from app.config import get_data_dir
from app.services.backup import session_db_path

_write_lock = threading.Lock()
_last_disk_write = 0.0
_MIN_INTERVAL_S = 0.25
SUCCESS_BANNER_S = 8.0
ERROR_BANNER_S = 45.0


@dataclass
class ImportProgress:
    status: str = "idle"
    phase: str = ""
    source_type: str = ""
    kind: str = ""
    current: int = 0
    total: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0
    review: int = 0
    failed: int = 0
    ignored: int = 0
    current_name: str = ""
    message: str = ""
    run_id: int = 0
    updated_at: float = 0.0

    @property
    def running(self) -> bool:
        return self.status == "running"

    @property
    def percent(self) -> int:
        if self.total <= 0:
            return 0
        return min(100, int(100 * self.current / self.total))

    @property
    def show_banner(self) -> bool:
        """Panel nahoře: během běhu, po dokončení jen chvíli, po chybě o něco déle."""
        if self.running:
            return True
        age = time.time() - self.updated_at if self.updated_at > 0 else 1e9
        if self.status in ("applied", "preview"):
            return age < SUCCESS_BANNER_S
        if self.status in ("failed", "rolled_back"):
            return age < ERROR_BANNER_S
        return False


_FIELD_NAMES = {item.name for item in fields(ImportProgress)}


def progress_path(data_dir: Path | None = None) -> Path:
    return (data_dir or get_data_dir()) / "cache" / "import_progress.json"


def preview_page_path(data_dir: Path | None = None) -> Path:
    return (data_dir or get_data_dir()) / "cache" / "import_preview_last.json"


def data_dir_for_session(session: Session) -> Path:
    try:
        return session_db_path(session).parent
    except RuntimeError:
        return get_data_dir()


def read_progress(data_dir: Path | None = None) -> ImportProgress:
    path = progress_path(data_dir)
    if not path.is_file():
        return ImportProgress()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ImportProgress()
    if not isinstance(payload, dict):
        return ImportProgress()
    known = {key: payload[key] for key in _FIELD_NAMES if key in payload}
    return ImportProgress(**known)


def write_progress(
    *,
    data_dir: Path | None = None,
    force: bool = False,
    **values: object,
) -> ImportProgress:
    """Aktualizuje JSON. Disk se zapisuje nejvýš 4× za sekundu, pokud není force."""
    global _last_disk_write
    directory = data_dir or get_data_dir()
    with _write_lock:
        current = read_progress(directory)
        if "updated_at" not in values:
            values = {**values, "updated_at": time.time()}
        for key, value in values.items():
            if key not in _FIELD_NAMES:
                raise TypeError(f"Neznámé pole průběhu: {key}")
            setattr(current, key, value)
        now = time.monotonic()
        if not force and now - _last_disk_write < _MIN_INTERVAL_S:
            return current
        try:
            _atomic_write(progress_path(directory), asdict(current))
        except OSError:
            # Windows: HTMX může mít JSON otevřený, os.replace pak selže.
            # Průběh nesmí shodit import.
            return current
        _last_disk_write = now
        return current


def save_preview_page(
    *,
    source_label: str,
    apply_action: str,
    apply_hidden: dict[str, str],
    without_gps: int,
    result: object,
    data_dir: Path | None = None,
) -> Path:
    path = preview_page_path(data_dir)
    _atomic_write(
        path,
        {
            "source_label": source_label,
            "apply_action": apply_action,
            "apply_hidden": apply_hidden,
            "without_gps": without_gps,
            "result": asdict(result) if is_dataclass(result) and not isinstance(result, type) else result,
        },
    )
    return path


def load_preview_page(data_dir: Path | None = None) -> dict | None:
    path = preview_page_path(data_dir)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or "result" not in payload:
        return None
    return payload


def _atomic_write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False)
        last_error: OSError | None = None
        for attempt in range(8):
            try:
                os.replace(tmp, path)
                return
            except PermissionError as exc:
                last_error = exc
                time.sleep(0.05 * (attempt + 1))
        if last_error is not None:
            raise last_error
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
