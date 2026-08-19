"""Samostatná FastAPI jen pro domácí Wi-Fi. Žádný katalogový editor, žádná záloha."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.status import HTTP_303_SEE_OTHER, HTTP_403_FORBIDDEN

from app.db.session import get_session
from app.services.catalog_export import export_catalog
from app.services.diary_bundle import MAX_UPLOAD_BYTES, parse_diary_upload
from app.services.diary_io import export_diary_zip, import_diary
from app.services.diary_schema import DiarySchemaError
from app.services.lan_sync import (
    COOKIE_NAME,
    current_token,
    pin_matches,
    remaining_seconds,
    session_is_active,
    token_is_valid,
)
from app.web.templating import templates

STATIC_DIR = Path(__file__).resolve().parent / "static"

lan_app = FastAPI(title="Památky — domácí síť", docs_url=None, redoc_url=None, openapi_url=None)
lan_app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


def _unlocked(request: Request) -> bool:
    return token_is_valid(request.cookies.get(COOKIE_NAME))


def _html(request: Request, name: str, context: dict, status_code: int = 200) -> HTMLResponse:
    payload = {
        "unlocked": _unlocked(request),
        "active": session_is_active(),
        "remaining_seconds": remaining_seconds(),
        "error": None,
        "result": None,
        "filename": None,
        "photo_count": 0,
        **context,
    }
    return templates.TemplateResponse(request, name, payload, status_code=status_code)


@lan_app.get("/lan", response_class=HTMLResponse)
def lan_home(request: Request) -> HTMLResponse:
    if not session_is_active():
        return _html(
            request,
            "lan/sync.html",
            {"error": "Domácí síť není zapnutá. Zapněte ji na PC."},
            HTTP_403_FORBIDDEN,
        )
    return _html(request, "lan/sync.html", {})


@lan_app.post("/lan/unlock")
def lan_unlock(request: Request, pin: str = Form("")) -> Response:
    if not session_is_active():
        return _html(
            request,
            "lan/sync.html",
            {"error": "Domácí síť není zapnutá. Zapněte ji na PC."},
            HTTP_403_FORBIDDEN,
        )
    if not pin_matches(pin):
        return _html(
            request,
            "lan/sync.html",
            {"error": "PIN nesedí. Přepište číslo z obrazovky PC."},
            HTTP_403_FORBIDDEN,
        )
    token = current_token()
    if not token:
        return _html(
            request,
            "lan/sync.html",
            {"error": "Domácí síť není zapnutá. Zapněte ji na PC."},
            HTTP_403_FORBIDDEN,
        )
    response = RedirectResponse("/lan", status_code=HTTP_303_SEE_OTHER)
    response.set_cookie(
        COOKIE_NAME,
        token,
        max_age=remaining_seconds() or 1,
        httponly=True,
        samesite="lax",
        path="/",
    )
    return response


@lan_app.post("/lan/import", response_class=HTMLResponse)
async def lan_import(request: Request, file: UploadFile = File(...)) -> HTMLResponse:
    if not session_is_active() or not _unlocked(request):
        return _html(request, "lan/sync.html", {"error": "Zadejte PIN z obrazovky PC."}, HTTP_403_FORBIDDEN)
    raw = await file.read(MAX_UPLOAD_BYTES + 1)
    session = get_session()
    try:
        try:
            data, photo_count = parse_diary_upload(raw, file.filename)
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
            return _html(
                request,
                "lan/sync.html",
                {"error": f"Soubor se nepodařilo přečíst: {exc}", "filename": file.filename},
                400,
            )
        try:
            result = import_diary(session, data)
        except DiarySchemaError as exc:
            return _html(request, "lan/sync.html", {"error": str(exc), "filename": file.filename}, 400)
        return _html(
            request,
            "lan/sync.html",
            {"result": result, "filename": file.filename, "photo_count": photo_count},
        )
    finally:
        session.close()


@lan_app.get("/lan/diary.zip")
def lan_diary_zip(request: Request) -> Response:
    if not session_is_active() or not _unlocked(request):
        return _html(request, "lan/sync.html", {"error": "Zadejte PIN z obrazovky PC."}, HTTP_403_FORBIDDEN)
    session = get_session()
    try:
        payload = export_diary_zip(session)
    finally:
        session.close()
    return Response(
        content=payload,
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="diary.zip"'},
    )


@lan_app.get("/lan/catalog.json")
def lan_catalog(request: Request) -> Response:
    if not session_is_active() or not _unlocked(request):
        return _html(request, "lan/sync.html", {"error": "Zadejte PIN z obrazovky PC."}, HTTP_403_FORBIDDEN)
    session = get_session()
    try:
        result = export_catalog(session)
    finally:
        session.close()
    return FileResponse(
        path=result.path,
        media_type="application/json; charset=utf-8",
        filename="catalog.json",
    )
