"""Výlety v PC deníku."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from starlette.status import HTTP_303_SEE_OTHER, HTTP_404_NOT_FOUND

from app.db.models import Place
from app.deps import db_session
from app.services.places import get_place_by_public_id
from app.services.trips import (
    TripInputError,
    add_stop,
    consecutive_stop_km,
    create_trip,
    default_trip_name,
    get_trip,
    list_trips,
    move_stop,
    remove_stop,
    soft_delete_trip,
    update_trip,
)
from app.web.templating import templates

router = APIRouter()

NOTICES = {
    "trip_created": "Výlet je založený.",
    "trip_updated": "Výlet je uložený.",
    "trip_deleted": "Výlet je smazaný. Záznam zůstává v deníku a přenese se při exportu.",
    "stop_added": "Zastávka je na výletu.",
}


def _notice(request: Request) -> str | None:
    key = request.query_params.get("notice")
    return NOTICES.get(key) if key else None


@router.get("/trips", response_class=HTMLResponse)
def trips_page(request: Request, session: Session = Depends(db_session)) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "trips/list.html",
        {
            "trips": list_trips(session),
            "notice": _notice(request),
            "form_name": default_trip_name(),
            "form_planned_on": "",
            "errors": {},
        },
    )


@router.post("/trips", response_class=HTMLResponse)
async def trips_create(request: Request, session: Session = Depends(db_session)) -> HTMLResponse:
    form = await request.form()
    name = str(form.get("name") or "").strip()
    planned_on = str(form.get("planned_on") or "").strip()
    try:
        trip = create_trip(session, name=name, planned_on=planned_on or None)
    except TripInputError as exc:
        return templates.TemplateResponse(
            request,
            "trips/list.html",
            {
                "trips": list_trips(session),
                "notice": None,
                "form_name": name or default_trip_name(),
                "form_planned_on": planned_on,
                "errors": {"form": str(exc)},
            },
            status_code=400,
        )
    return RedirectResponse(f"/trips/{trip.public_id}?notice=trip_created", status_code=HTTP_303_SEE_OTHER)


@router.get("/trips/{public_id}", response_class=HTMLResponse)
def trip_detail(request: Request, public_id: str, session: Session = Depends(db_session)) -> HTMLResponse:
    trip = get_trip(session, public_id)
    if trip is None or trip.is_deleted:
        return templates.TemplateResponse(
            request,
            "trips/not_found.html",
            {"public_id": public_id},
            status_code=HTTP_404_NOT_FOUND,
        )
    q = (request.query_params.get("q") or "").strip()
    suggestions: list[Place] = []
    if q:
        term = f"%{q}%"
        already = {stop.place_public_id for stop in trip.stops}
        stmt = (
            select(Place)
            .where(Place.archived_at.is_(None))
            .where(or_(Place.name.ilike(term), Place.municipality.ilike(term), Place.alternative_names.ilike(term)))
            .order_by(Place.name.asc())
            .limit(20)
        )
        if already:
            stmt = stmt.where(Place.public_id.notin_(already))
        suggestions = list(session.scalars(stmt).all())[:12]
    stops = sorted(trip.stops, key=lambda item: item.sort_order)
    return templates.TemplateResponse(
        request,
        "trips/detail.html",
        {
            "trip": trip,
            "stops": stops,
            "gaps": consecutive_stop_km(trip),
            "suggestions": suggestions,
            "q": q,
            "notice": _notice(request),
        },
    )


@router.post("/trips/{public_id}", response_class=HTMLResponse)
async def trip_update(
    request: Request, public_id: str, session: Session = Depends(db_session)
) -> HTMLResponse:
    trip = get_trip(session, public_id)
    if trip is None or trip.is_deleted:
        return RedirectResponse("/trips", status_code=HTTP_303_SEE_OTHER)
    form = await request.form()
    try:
        update_trip(
            session,
            trip,
            name=str(form.get("name") or ""),
            planned_on=str(form.get("planned_on") or "").strip() or None,
            notes=str(form.get("notes") or ""),
        )
    except TripInputError:
        return RedirectResponse(f"/trips/{public_id}", status_code=HTTP_303_SEE_OTHER)
    return RedirectResponse(f"/trips/{public_id}?notice=trip_updated", status_code=HTTP_303_SEE_OTHER)


@router.post("/trips/{public_id}/delete")
def trip_delete(public_id: str, session: Session = Depends(db_session)) -> RedirectResponse:
    trip = get_trip(session, public_id)
    if trip is not None:
        soft_delete_trip(session, trip)
    return RedirectResponse("/trips?notice=trip_deleted", status_code=HTTP_303_SEE_OTHER)


@router.post("/trips/{public_id}/stops")
async def trip_add_stop(
    request: Request, public_id: str, session: Session = Depends(db_session)
) -> RedirectResponse:
    trip = get_trip(session, public_id)
    if trip is None or trip.is_deleted:
        return RedirectResponse("/trips", status_code=HTTP_303_SEE_OTHER)
    form = await request.form()
    place_id = str(form.get("place_public_id") or "").strip()
    place = get_place_by_public_id(session, place_id)
    if place is not None:
        add_stop(session, trip, place)
    return RedirectResponse(f"/trips/{public_id}?notice=stop_added", status_code=HTTP_303_SEE_OTHER)


@router.post("/trips/{public_id}/stops/{place_public_id}/delete")
def trip_remove_stop(
    public_id: str, place_public_id: str, session: Session = Depends(db_session)
) -> RedirectResponse:
    trip = get_trip(session, public_id)
    if trip is None or trip.is_deleted:
        return RedirectResponse("/trips", status_code=HTTP_303_SEE_OTHER)
    remove_stop(session, trip, place_public_id)
    return RedirectResponse(f"/trips/{public_id}", status_code=HTTP_303_SEE_OTHER)


@router.post("/trips/{public_id}/stops/{place_public_id}/up")
def trip_stop_up(
    public_id: str, place_public_id: str, session: Session = Depends(db_session)
) -> RedirectResponse:
    trip = get_trip(session, public_id)
    if trip is not None and not trip.is_deleted:
        move_stop(session, trip, place_public_id, -1)
    return RedirectResponse(f"/trips/{public_id}", status_code=HTTP_303_SEE_OTHER)


@router.post("/trips/{public_id}/stops/{place_public_id}/down")
def trip_stop_down(
    public_id: str, place_public_id: str, session: Session = Depends(db_session)
) -> RedirectResponse:
    trip = get_trip(session, public_id)
    if trip is not None and not trip.is_deleted:
        move_stop(session, trip, place_public_id, 1)
    return RedirectResponse(f"/trips/{public_id}", status_code=HTTP_303_SEE_OTHER)
