from __future__ import annotations

import json

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.status import HTTP_303_SEE_OTHER, HTTP_404_NOT_FOUND

from app.config import get_database_path
from app.db.models import Place
from app.services.backup import list_backups
from app.deps import db_session
from app.services.catalog_export import catalog_export_status, export_catalog
from app.services.diary_io import (
    VisitInputError,
    VisitFilters,
    add_visit,
    diary_export_status,
    export_diary,
    get_visit_for_place,
    import_diary,
    list_open_diary_issues,
    list_visits,
    list_visits_for_place,
    parse_rating,
    save_journal_state,
    soft_delete_visit,
    today_iso_date,
    update_visit,
)
from app.services.diary_schema import DiarySchemaError
from app.services.merge_places import MergeError, find_merge_candidates, merge_places
from app.services.places import (
    PlaceFilters,
    PlaceInput,
    SORT_CHOICES,
    all_place_types,
    archive_place,
    create_place,
    dashboard_stats,
    distinct_locations,
    filter_facet_counts,
    form_context,
    get_place_by_public_id,
    list_places,
    restore_place,
    update_place,
)
from app.services.geo import (
    MAX_RADIUS_KM,
    MIN_RADIUS_KM,
    RADIUS_STEP_KM,
    clamp_radius_km,
)
from app.services.nearby import NearbyResult, list_nearby, resolve_origin, suggest_origins
from app.web.templating import templates

router = APIRouter()

NOTICES = {
    "created": "Místo bylo založeno.",
    "updated": "Změny jsou uložené.",
    "archived": "Místo je v archivu. Záznam i public_id zůstaly.",
    "restored": "Místo je znovu aktivní.",
    "merged": "Záznam byl sloučen. public_id se nezměnilo.",
    "created_new": "Bylo založeno nové místo.",
    "keep_master": "Master hodnota zůstává, override platí dál.",
    "take_source": "Převzata hodnota ze zdroje, override byl zrušen.",
    "places_merged": "Místa byla sloučena. Vítězné public_id zůstalo.",
    "merge_error": "Sloučení se nepovedlo.",
    "exported": "Katalog byl exportován do catalog.json.",
    "diary_exported": "Deník byl exportován do diary.json.",
    "visit_added": "Návštěva je uložená.",
    "visit_updated": "Návštěva je upravená.",
    "visit_deleted": "Návštěva je smazaná. Záznam zůstává v deníku a přenese se při exportu.",
    "journal_saved": "Osobní stav deníku je uložený.",
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
            "export_status": catalog_export_status(session),
            "diary_status": diary_export_status(session),
            "diary_issues": list_open_diary_issues(session),
            "backup_count": len(list_backups(get_database_path())),
            "notice": _notice(request),
        },
    )


@router.get("/visits", response_class=HTMLResponse)
def visits_page(request: Request, session: Session = Depends(db_session)) -> HTMLResponse:
    filters = VisitFilters.from_query(request.query_params)
    result = list_visits(session, filters)
    return templates.TemplateResponse(
        request,
        "visits/list.html",
        {
            "filters": filters,
            "result": result,
            "notice": _notice(request),
        },
    )


@router.post("/catalog/export")
def catalog_export(session: Session = Depends(db_session)) -> FileResponse:
    result = export_catalog(session)
    return FileResponse(
        path=result.path,
        media_type="application/json; charset=utf-8",
        filename="catalog.json",
    )


@router.post("/diary/export")
def diary_export_route(session: Session = Depends(db_session)) -> FileResponse:
    result = export_diary(session)
    return FileResponse(
        path=result.path,
        media_type="application/json; charset=utf-8",
        filename="diary.json",
    )


@router.post("/diary/import", response_class=HTMLResponse)
async def diary_import_route(
    request: Request,
    session: Session = Depends(db_session),
    file: UploadFile = File(...),
) -> HTMLResponse:
    raw = await file.read()
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return templates.TemplateResponse(
            request,
            "diary/import_result.html",
            {"error": f"Soubor není platný JSON: {exc}", "result": None, "filename": file.filename},
            status_code=400,
        )
    try:
        result = import_diary(session, data)
    except DiarySchemaError as exc:
        return templates.TemplateResponse(
            request,
            "diary/import_result.html",
            {"error": str(exc), "result": None, "filename": file.filename},
            status_code=400,
        )
    return templates.TemplateResponse(
        request,
        "diary/import_result.html",
        {"error": None, "result": result, "filename": file.filename},
    )


def _nearby_markers(result: NearbyResult) -> list[dict]:
    return [
        {
            "id": hit.place.public_id,
            "name": hit.place.name,
            "lat": hit.place.latitude,
            "lon": hit.place.longitude,
            "km": round(hit.km, 2),
            "visited": hit.visited,
            "want": hit.want_to_visit,
        }
        for hit in result.hits
        if hit.place.latitude is not None and hit.place.longitude is not None
    ]


@router.get("/nearby", response_class=HTMLResponse)
def nearby_page(request: Request, session: Session = Depends(db_session)) -> HTMLResponse:
    params = request.query_params
    q = (params.get("q") or "").strip()
    lat = (params.get("lat") or "").strip()
    lon = (params.get("lon") or "").strip()
    origin_label = (params.get("origin_label") or "").strip()
    type_code = (params.get("type") or "").strip()
    visitability = (params.get("visitability") or "").strip()
    journal = (params.get("journal") or "").strip()
    radius_km = clamp_radius_km(params.get("radius_km"))
    origin = resolve_origin(session, lat=lat, lon=lon, q=q, origin_label=origin_label)
    if origin is not None:
        result = list_nearby(
            session,
            origin,
            radius_km=radius_km,
            type_code=type_code,
            visitability=visitability,
            journal=journal,
        )
        lat = f"{origin.latitude:.6f}".rstrip("0").rstrip(".")
        lon = f"{origin.longitude:.6f}".rstrip("0").rstrip(".")
        origin_label = origin.label
    else:
        error = None
        if q or lat or lon:
            error = "Místo se nepodařilo najít. Zkuste jiný název, nebo zadejte souřadnice."
        result = NearbyResult(origin=None, radius_km=radius_km, hits=[], skipped_no_gps=0, error=error)
    return templates.TemplateResponse(
        request,
        "nearby.html",
        {
            "q": q,
            "lat": lat,
            "lon": lon,
            "origin_label": origin_label,
            "radius_km": radius_km,
            "radius_min": MIN_RADIUS_KM,
            "radius_max": MAX_RADIUS_KM,
            "radius_step": RADIUS_STEP_KM,
            "type_code": type_code,
            "visitability": visitability,
            "visitability_counts": None,
            "journal": journal,
            "result": result,
            "map_data": (
                {
                    "lat": result.origin.latitude,
                    "lon": result.origin.longitude,
                    "radius": result.radius_km,
                    "markers": _nearby_markers(result),
                }
                if result.origin is not None
                else None
            ),
            "place_types": all_place_types(session),
            **form_context(),
        },
    )


@router.get("/nearby/suggest", response_class=HTMLResponse)
def nearby_suggest(request: Request, session: Session = Depends(db_session)) -> HTMLResponse:
    params = request.query_params
    return templates.TemplateResponse(
        request,
        "nearby/_suggest.html",
        {
            "suggestions": suggest_origins(session, params.get("q") or ""),
            "radius_km": clamp_radius_km(params.get("radius_km")),
            "type_code": (params.get("type") or "").strip(),
            "visitability": (params.get("visitability") or "").strip(),
            "journal": (params.get("journal") or "").strip(),
        },
    )


@router.get("/places", response_class=HTMLResponse)
def places_list(request: Request, session: Session = Depends(db_session)) -> HTMLResponse:
    filters = PlaceFilters.from_query(request.query_params)
    result = list_places(session, filters)
    counts = filter_facet_counts(session, filters)
    locations = distinct_locations(session, filters, counts)
    return templates.TemplateResponse(
        request,
        "places/list.html",
        {
            "filters": filters,
            "result": result,
            "place_types": all_place_types(session),
            "sort_choices": SORT_CHOICES,
            "notice": _notice(request),
            "catalog_empty": (session.scalar(select(func.count()).select_from(Place)) or 0) == 0,
            "facet_counts": counts,
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


def _empty_visit_form() -> dict[str, str | dict[str, str]]:
    return {"visited_at": today_iso_date(), "rating": "", "people": "", "note": "", "errors": {}}


def _visit_form_from_visit(visit) -> dict[str, str | dict[str, str]]:
    return {
        "visited_at": visit.visited_at or today_iso_date(),
        "rating": str(visit.rating) if visit.rating else "",
        "people": ", ".join(visit.people),
        "note": visit.note or "",
        "errors": {},
    }


def _place_detail_context(
    request: Request,
    session: Session,
    place,
    *,
    visit_form: dict[str, str | dict[str, str]] | None = None,
    editing_visit_id: str | None = None,
) -> dict:
    edit_id = editing_visit_id or (request.query_params.get("edit") or "").strip() or None
    form = visit_form
    if form is None and edit_id:
        visit = get_visit_for_place(session, place, edit_id)
        if visit is not None and not visit.is_deleted:
            form = _visit_form_from_visit(visit)
        else:
            edit_id = None
    return {
        "place": place,
        "visits": list_visits_for_place(session, place),
        "journal_state": place.journal_state,
        "notice": _notice(request),
        "visit_form": form or _empty_visit_form(),
        "editing_visit_id": edit_id,
        **form_context(),
    }


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
        _place_detail_context(request, session, place),
    )


def _visit_fields_from_form(form) -> dict[str, str | dict[str, str]]:
    return {
        "visited_at": str(form.get("visited_at") or "").strip(),
        "rating": str(form.get("rating") or "").strip(),
        "people": str(form.get("people") or ""),
        "note": str(form.get("note") or ""),
        "errors": {},
    }


def _visit_form_error_response(
    request: Request,
    session: Session,
    place,
    visit_form: dict[str, str | dict[str, str]],
    exc: VisitInputError,
    *,
    editing_visit_id: str | None = None,
):
    errors = visit_form["errors"]
    assert isinstance(errors, dict)
    message = str(exc)
    if "Datum" in message or "datum" in message:
        errors["visited_at"] = message
    elif "Hodnocení" in message:
        errors["rating"] = message
    else:
        errors["form"] = message
    return templates.TemplateResponse(
        request,
        "places/detail.html",
        _place_detail_context(
            request, session, place, visit_form=visit_form, editing_visit_id=editing_visit_id
        ),
        status_code=400,
    )


@router.post("/places/{public_id}/visits", response_class=HTMLResponse)
async def places_add_visit(
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
    visit_form = _visit_fields_from_form(await request.form())
    try:
        rating = parse_rating(str(visit_form["rating"]))
        add_visit(
            session,
            place,
            visited_at=str(visit_form["visited_at"]) or None,
            rating=rating,
            people=str(visit_form["people"]),
            note=str(visit_form["note"]),
        )
    except VisitInputError as exc:
        return _visit_form_error_response(request, session, place, visit_form, exc)
    return RedirectResponse(f"/places/{public_id}?notice=visit_added", status_code=HTTP_303_SEE_OTHER)


@router.post("/places/{public_id}/visits/{visit_public_id}", response_class=HTMLResponse)
async def places_update_visit(
    request: Request, public_id: str, visit_public_id: str, session: Session = Depends(db_session)
) -> HTMLResponse:
    place = get_place_by_public_id(session, public_id)
    if place is None:
        return templates.TemplateResponse(
            request,
            "places/not_found.html",
            {"public_id": public_id},
            status_code=HTTP_404_NOT_FOUND,
        )
    visit = get_visit_for_place(session, place, visit_public_id)
    if visit is None or visit.is_deleted:
        return RedirectResponse(f"/places/{public_id}?notice=visit_deleted", status_code=HTTP_303_SEE_OTHER)
    visit_form = _visit_fields_from_form(await request.form())
    try:
        rating = parse_rating(str(visit_form["rating"]))
        update_visit(
            session,
            visit,
            visited_at=str(visit_form["visited_at"]) or None,
            rating=rating,
            people=str(visit_form["people"]),
            note=str(visit_form["note"]),
        )
    except VisitInputError as exc:
        return _visit_form_error_response(
            request, session, place, visit_form, exc, editing_visit_id=visit_public_id
        )
    return RedirectResponse(f"/places/{public_id}?notice=visit_updated", status_code=HTTP_303_SEE_OTHER)


@router.post("/places/{public_id}/visits/{visit_public_id}/delete")
def places_delete_visit(
    public_id: str, visit_public_id: str, session: Session = Depends(db_session)
) -> RedirectResponse:
    place = get_place_by_public_id(session, public_id)
    if place is None:
        return RedirectResponse("/places", status_code=HTTP_303_SEE_OTHER)
    visit = get_visit_for_place(session, place, visit_public_id)
    if visit is not None:
        soft_delete_visit(session, visit)
    return RedirectResponse(f"/places/{public_id}?notice=visit_deleted", status_code=HTTP_303_SEE_OTHER)


@router.post("/places/{public_id}/journal")
async def places_save_journal(
    request: Request, public_id: str, session: Session = Depends(db_session)
) -> RedirectResponse:
    place = get_place_by_public_id(session, public_id)
    if place is None:
        return RedirectResponse("/places", status_code=HTTP_303_SEE_OTHER)
    form = await request.form()
    save_journal_state(
        session,
        place,
        want_to_visit=bool(form.get("want_to_visit")),
        favorite=bool(form.get("favorite")),
        personal_note=str(form.get("personal_note") or ""),
    )
    return RedirectResponse(f"/places/{public_id}?notice=journal_saved", status_code=HTTP_303_SEE_OTHER)


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
    try:
        restore_place(session, place)
    except ValueError:
        return RedirectResponse(f"/places/{public_id}?notice=merge_error", status_code=HTTP_303_SEE_OTHER)
    return RedirectResponse(f"/places/{public_id}?notice=restored", status_code=HTTP_303_SEE_OTHER)


@router.get("/places/{public_id}/merge", response_class=HTMLResponse)
def places_merge_form(request: Request, public_id: str, session: Session = Depends(db_session)) -> HTMLResponse:
    place = get_place_by_public_id(session, public_id)
    if place is None:
        return templates.TemplateResponse(
            request,
            "places/not_found.html",
            {"public_id": public_id},
            status_code=HTTP_404_NOT_FOUND,
        )
    q = (request.query_params.get("q") or "").strip()
    candidates = find_merge_candidates(session, place, q)
    return templates.TemplateResponse(
        request,
        "places/merge.html",
        {
            "place": place,
            "candidates": candidates,
            "q": q,
            "notice": _notice(request),
        },
    )


@router.post("/places/{public_id}/merge")
async def places_merge(request: Request, public_id: str, session: Session = Depends(db_session)):
    winner = get_place_by_public_id(session, public_id)
    if winner is None:
        return RedirectResponse("/places", status_code=HTTP_303_SEE_OTHER)
    form = await request.form()
    loser_id = str(form.get("loser_public_id") or "").strip()
    loser = get_place_by_public_id(session, loser_id)
    if loser is None:
        return RedirectResponse(f"/places/{public_id}/merge?notice=merge_error", status_code=HTTP_303_SEE_OTHER)
    try:
        merge_places(session, winner, loser)
    except MergeError:
        return RedirectResponse(f"/places/{public_id}/merge?notice=merge_error", status_code=HTTP_303_SEE_OTHER)
    return RedirectResponse(f"/places/{public_id}?notice=places_merged", status_code=HTTP_303_SEE_OTHER)
