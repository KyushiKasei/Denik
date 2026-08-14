from __future__ import annotations

import sys
from pathlib import Path

from alembic import command
from alembic.config import Config

from app.config import PC_APP_DIR, sqlite_url


ALEMBIC_INI = PC_APP_DIR / "alembic.ini"


def run_migrations(db_path: Path) -> None:
    if str(PC_APP_DIR) not in sys.path:
        sys.path.insert(0, str(PC_APP_DIR))
    cfg = Config(str(ALEMBIC_INI))
    cfg.set_main_option("script_location", str(PC_APP_DIR / "migrations"))
    url = sqlite_url(db_path).replace("%", "%%")
    cfg.set_main_option("sqlalchemy.url", url)
    command.upgrade(cfg, "head")
