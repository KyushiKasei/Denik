from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.config import DEFAULT_PORT, ensure_data_dir, get_database_path
from app.db.migrate import run_migrations
from app.db.seed import seed_place_types
from app.db.session import get_engine, make_session_factory
from app.logging_setup import setup_logging
from app.web.routers.catalog import router as catalog_router

STATIC_DIR = Path(__file__).resolve().parent / "web" / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    ensure_data_dir()
    setup_logging()
    db_path = get_database_path()
    run_migrations(db_path)
    engine = get_engine()
    session = make_session_factory(engine)()
    try:
        seed_place_types(session)
    finally:
        session.close()
    yield


app = FastAPI(title="Památky — katalog", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(catalog_router)


def run() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=DEFAULT_PORT, reload=False)
