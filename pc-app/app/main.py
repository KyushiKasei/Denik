from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

import anyio
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.config import DEFAULT_PORT, ensure_data_dir, get_database_path
from app.db.migrate import run_migrations
from app.db.seed import seed_place_types
from app.db.session import get_engine, make_session_factory
from app.logging_setup import get_logger, setup_logging
from app.web.routers.backup import router as backup_router
from app.web.routers.catalog import router as catalog_router
from app.web.routers.imports import router as imports_router
from app.web.routers.trips import router as trips_router

STATIC_DIR = Path(__file__).resolve().parent / "web" / "static"


def _startup() -> None:
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


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await anyio.to_thread.run_sync(_startup)
    yield


app = FastAPI(title="Památky — katalog", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(catalog_router)
app.include_router(trips_router)
app.include_router(backup_router)
app.include_router(imports_router)


@app.exception_handler(Exception)
async def unhandled_error(request: Request, exc: Exception) -> HTMLResponse:
    get_logger().exception("%s %s", request.method, request.url.path)
    return HTMLResponse("Došlo k chybě. Zkuste to znovu, nebo se podívejte do protokolu aplikace.", status_code=500)


def run() -> None:
    import uvicorn

    uvicorn.run("app.main:app", host="127.0.0.1", port=DEFAULT_PORT, reload=False)
