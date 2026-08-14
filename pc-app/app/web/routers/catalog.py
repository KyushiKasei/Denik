from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from starlette.status import HTTP_303_SEE_OTHER, HTTP_404_NOT_FOUND

from app.config import get_database_path
from app.db.enums import items, label
from app.deps import db_session
from app.services.places import (
    PlaceFilters,
    PlaceInput,
    SORT_CHOICES,
    all_place_types,
    archive_place,
    create_place,
    dashboard_stats,
    distinct_locations,
    form_context,
    get_place_by_public_id,
    list_places,
    restore_place,
    update_place,
)

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
templates.env.globals["enum_label"] = label
templates.env.globals["place_type_items"] = lambda: items("place_types")

router = APIRouter()

NOTICES = {
    "created": "Místo bylo založeno.",
    "updated": "Změny jsou uložené.",
    "archived": "Místo je v archivu. Záznam i public_id zůstaly.",
    "restored": "Místo je znovu aktivní.",
}


def _notice(request: Request) -> str | None:
    key = request.query_params.get("notice")
    return NOTICES.get(key) if key else None


@router.get("/", response_class=HTMLResponse)
def dashboard(request: Request, session: Session = Depends(db_session)) -> HTMLResponse:
    stats = dashboard_stats(session)
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "stats": stats,
            "db_path": str(get_database_path()),
        },
    )


@router.get("/places", response_class=HTMLResponse)
def places_list(request: Request, session: Session = Depends(db_session)) -> HTMLResponse:
    filters = PlaceFilters.from_query(request.query_params)
    result = list_places(session, filters)
    locations = distinct_locations(session)
    return templates.TemplateResponse(
        request,
        "places/list.html",
        {
            "filters": filters,
            "result": result,
            "place_types": all_place_types(session),
            "sort_choices": SORT_CHOICES,
            "notice": _notice(request),
            **locations,
            **form_context(),
        },
    )


@router.get("/places/new", response_class=HTMLResponse)
def places_new(request: Request, session: Session = Depends(db_session)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "places/form.html",
        {
            "place": None,
            "form": PlaceInput(),
            "place_types": all_place_types(session),
            **form_context(),
        },
    )


@router.post("/places", response_class=HTMLResponse)
async def places_create(request: Request, session: Session = Depends(db_session)) -> HTMLResponse:
    form = await request.form()
    data = PlaceInput.from_form(form)
    if not data.validate():
        return templates.TemplateResponse(
            request,
            "places/form.html",
            {
                "place": None,
                "form": data,
                "place_types": all_place_types(session),
                **form_context(),
            },
            status_code=400,
        )
    place = create_place(session, data)
    return RedirectResponse(f"/places/{place.public_id}?notice=created", status_code=HTTP_303_SEE_OTHER)


@router.get("/places/{public_id}", response_class=HTMLResponse)
def places_detail(request: Request, public_id: str, session: Session = Depends(db_session)) -> HTMLResponse:
    place = get_place_by_public_id(session, public_id)
    if place is None:
        return templates.TemplateResponse(
            request,
            "places/not_found.html",
            {"public_id": public_id},
            status_code=HTTP_404_NOT_FOUND,
        )
    return templates.TemplateResponse(
        request,
        "places/detail.html",
        {
            "place": place,
            "notice": _notice(request),
            **form_context(),
        },
    )


@router.get("/places/{public_id}/edit", response_class=HTMLResponse)
def places_edit(request: Request, public_id: str, session: Session = Depends(db_session)) -> HTMLResponse:
    place = get_place_by_public_id(session, public_id)
    if place is None:
        return templates.TemplateResponse(
            request,
            "places/not_found.html",
            {"public_id": public_id},
            status_code=HTTP_404_NOT_FOUND,
        )
    return templates.TemplateResponse(
        request,
        "places/form.html",
        {
            "place": place,
            "form": PlaceInput.from_place(place),
            "place_types": all_place_types(session),
            **form_context(),
        },
    )


@router.post("/places/{public_id}", response_class=HTMLResponse)
async def places_update(
    request: Request, public_id: str, session: Session = Depends(db_session)
) -> HTMLResponse:
    place = get_place_by_public_id(session, public_id)
    if place is None:
        return templates.TemplateResponse(
            request,
            "places/not_found.html",
            {"public_id": public_id},
            status_code=HTTP_404_NOT_FOUND,
        )
    form = await request.form()
    data = PlaceInput.from_form(form)
    if not data.validate():
        return templates.TemplateResponse(
            request,
            "places/form.html",
            {
                "place": place,
                "form": data,
                "place_types": all_place_types(session),
                **form_context(),
            },
            status_code=400,
        )
    update_place(session, place, data)
    return RedirectResponse(f"/places/{public_id}?notice=updated", status_code=HTTP_303_SEE_OTHER)


@router.post("/places/{public_id}/archive")
def places_archive(public_id: str, session: Session = Depends(db_session)):
    place = get_place_by_public_id(session, public_id)
    if place is None:
        return RedirectResponse("/places", status_code=HTTP_303_SEE_OTHER)
    archive_place(session, place)
    return RedirectResponse(f"/places/{public_id}?notice=archived", status_code=HTTP_303_SEE_OTHER)


@router.post("/places/{public_id}/restore")
def places_restore(public_id: str, session: Session = Depends(db_session)):
    place = get_place_by_public_id(session, public_id)
    if place is None:
        return RedirectResponse("/places", status_code=HTTP_303_SEE_OTHER)
    restore_place(session, place)
    return RedirectResponse(f"/places/{public_id}?notice=restored", status_code=HTTP_303_SEE_OTHER)
