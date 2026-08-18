"""Zapnutí a vypnutí domácí relace z localhost dashboardu."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.status import HTTP_303_SEE_OTHER

from app.services.lan_sync import LanListenError, lan_status, start_lan_session, stop_lan_session
from app.web.templating import templates

router = APIRouter()


@router.post("/lan/enable")
def lan_enable() -> RedirectResponse:
    try:
        start_lan_session(listen=True)
    except LanListenError:
        return RedirectResponse("/?notice=lan_listen_error", status_code=HTTP_303_SEE_OTHER)
    return RedirectResponse("/?notice=lan_enabled", status_code=HTTP_303_SEE_OTHER)


@router.post("/lan/disable")
def lan_disable() -> RedirectResponse:
    stop_lan_session()
    return RedirectResponse("/?notice=lan_disabled", status_code=HTTP_303_SEE_OTHER)


@router.get("/lan/status", response_class=HTMLResponse)
def lan_status_fragment(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "lan/_panel.html", {"lan": lan_status()})
