"""Ruční záloha a obnova SQLite v PC UI."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from sqlalchemy.orm import Session
from starlette.status import HTTP_303_SEE_OTHER

from app.config import get_database_path
from app.deps import db_session
from app.services.backup import (
    BackupError,
    create_manual_backup,
    list_backups,
    resolve_backup_name,
    restore_from_path,
    save_uploaded_backup,
)
from app.services.diary_bundle import MAX_UPLOAD_BYTES
from app.web.templating import templates

router = APIRouter()

NOTICES = {
    "backed_up": "Záloha SQLite je hotová.",
    "restored_db": "Databáze byla obnovena ze zálohy. Katalog i deník na PC jsou ze zvoleného souboru.",
}


def _notice(request: Request) -> str | None:
    key = request.query_params.get("notice")
    return NOTICES.get(key) if key else None


def _page(request: Request, *, error: str | None = None, status_code: int = 200) -> HTMLResponse:
    db_path = get_database_path()
    return templates.TemplateResponse(
        request,
        "backup/index.html",
        {
            "db_path": str(db_path),
            "backups": list_backups(db_path),
            "notice": _notice(request) if error is None else None,
            "error": error,
        },
        status_code=status_code,
    )


@router.get("/backup", response_class=HTMLResponse)
def backup_page(request: Request) -> HTMLResponse:
    return _page(request)


@router.post("/backup/create")
def backup_create(session: Session = Depends(db_session)) -> RedirectResponse:
    create_manual_backup(session)
    return RedirectResponse("/backup?notice=backed_up", status_code=HTTP_303_SEE_OTHER)


@router.get("/backup/files/{filename}")
def backup_download(request: Request, filename: str):
    try:
        path = resolve_backup_name(filename, get_database_path())
    except BackupError:
        return _page(request, error="Záloha neexistuje.", status_code=404)
    return FileResponse(
        path=path,
        media_type="application/vnd.sqlite3",
        filename=path.name,
    )


@router.post("/backup/restore", response_model=None)
def backup_restore(request: Request, filename: str = Form(...)):
    db_path = get_database_path()
    try:
        source = resolve_backup_name(filename, db_path)
        restore_from_path(source, db_path)
    except BackupError as exc:
        return _page(request, error=str(exc), status_code=400)
    return RedirectResponse("/backup?notice=restored_db", status_code=HTTP_303_SEE_OTHER)


@router.post("/backup/restore-upload", response_model=None)
async def backup_restore_upload(request: Request, file: UploadFile = File(...)):
    db_path = get_database_path()
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(raw) > MAX_UPLOAD_BYTES:
        return _page(request, error="Soubor je větší než 80 MB.", status_code=400)
    try:
        saved = save_uploaded_backup(raw, db_path)
        restore_from_path(saved, db_path)
    except BackupError as exc:
        return _page(request, error=str(exc), status_code=400)
    return RedirectResponse("/backup?notice=restored_db", status_code=HTTP_303_SEE_OTHER)
