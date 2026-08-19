"""Import centrum, náhled/apply fixture, review fronta, override polí."""

from __future__ import annotations

import json
import math
from collections import Counter
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from starlette.status import HTTP_303_SEE_OTHER, HTTP_404_NOT_FOUND

from app.db.enums import label
from app.db.models import ImportFieldChange, ImportReview, ImportRun, Place
from app.deps import db_session
from app.importers.fixture import DEFAULT_FIXTURE, FIXTURE_DIR, list_fixture_files
from app.importers.official_web.parser import parse_public_ids
from app.services.apply_import import (
    ImportResult,
    RecordOutcome,
    resolve_create_new,
    resolve_ignore,
    resolve_merge,
    unignore_review,
)
from app.services.import_job import (
    job_is_running,
    run_fixture_apply,
    run_fixture_preview,
    run_named_apply,
    run_named_preview,
    run_review_reprocess,
    try_begin_job,
)
from app.services.import_progress import load_preview_page, read_progress
from app.services.matching import LEVEL_FILTER_OPTIONS, PREVIEW_OUTCOME_LIMIT, normalize_level_filter
from app.logging_setup import get_logger
from app.services.overrides import FIELD_LABELS_CS, keep_master, take_source
from app.services.places import get_place_by_public_id
from app.services.values import decode_value
from app.web.templating import templates

router = APIRouter()
_log = get_logger()

NOTICES = {
    "preview": "Náhled je hotový. Data se ještě nezapsala.",
    "applied": "Import byl zapsán.",
    "rolled_back": "Import selhal a byl vrácen zpět. Záloha zůstala.",
    "merged": "Záznam byl sloučen. public_id se nezměnilo.",
    "created_new": "Bylo založeno nové místo.",
    "ignored": "Položka je ignorovaná. Další import ji znovu neotevře.",
    "unignored": "Ignorace je zrušená.",
    "keep_master": "Master hodnota zůstává, override platí dál.",
    "take_source": "Převzata hodnota ze zdroje, override byl zrušen.",
    "sparql_failed": "Stažení z Wikidata selhalo. Katalog se nezměnil. Podrobnosti jsou v logu běhu.",
    "download_failed": "Stažení zdroje selhalo. Katalog se nezměnil. Podrobnosti jsou v logu běhu.",
    "import_running": "Import běží na pozadí. Katalog se aktualizuje až po dokončení.",
    "preview_running": "Náhled běží na pozadí. Katalog se nemění. Průběh je nahoře jako kolik z kolika.",
    "already_running": "Import už běží. Počkejte na dokončení.",
    "reprocess_running": "Přepočet fronty běží. Jisté položky se sloučí automaticky, OSM identita se připojí.",
    "reprocess_applied": "Fronta byla přepočtena. Jisté shody se sloučily, zbytek zůstal k rozhodnutí.",
    "merge_failed": "Sloučení selhalo. Podrobnosti jsou v logu. Zkuste to znovu.",
    "create_failed": "Nelze založit nové místo: toto externí ID už patří existujícímu místu. Sloučte ho tam, nebo položku ignorujte.",
}


def _notice(request: Request) -> str | None:
    key = request.query_params.get("notice")
    progress = read_progress()
    if key == "reprocess_running":
        if progress.status == "applied":
            return NOTICES["reprocess_applied"]
        if progress.status == "rolled_back":
            return NOTICES["rolled_back"]
        if progress.status == "failed":
            return progress.message or NOTICES["sparql_failed"]
        return NOTICES["reprocess_running"]
    if key in {"import_running", "preview_running"}:
        if progress.status == "applied":
            return NOTICES["applied"]
        if progress.status == "preview":
            return NOTICES["preview"]
        if progress.status == "rolled_back":
            return NOTICES["rolled_back"]
        if progress.status == "failed":
            return progress.message or NOTICES["sparql_failed"]
        if key == "preview_running":
            return NOTICES["preview_running"]
    return NOTICES.get(key) if key else None


def _open_review_count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(ImportReview).where(ImportReview.status == "open")) or 0


def _open_change_count(session: Session) -> int:
    return session.scalar(
        select(func.count()).select_from(ImportFieldChange).where(ImportFieldChange.status == "open")
    ) or 0


def _use_cache(form) -> bool:
    value = str(form.get("use_cache") or "").strip().lower()
    return value in {"1", "on", "true", "yes"}


def _public_ids_from_form(form) -> list[str] | None:
    ids = parse_public_ids(str(form.get("public_ids") or ""))
    return ids or None


def _result_from_preview_payload(payload: dict) -> ImportResult:
    raw = dict(payload["result"])
    outcomes = [RecordOutcome(**item) for item in raw.pop("outcomes", [])]
    return ImportResult(outcomes=outcomes, **raw)


def _fixture_path(name: str | None) -> Path:
    if not name:
        return DEFAULT_FIXTURE
    candidate = (FIXTURE_DIR / Path(name).name).resolve()
    if candidate.parent != FIXTURE_DIR.resolve() or not candidate.is_file():
        return DEFAULT_FIXTURE
    return candidate


def _nav(session: Session) -> dict:
    return {
        "open_review_count": _open_review_count(session),
        "open_change_count": _open_change_count(session),
        "enum_label": label,
        "field_labels": FIELD_LABELS_CS,
        "progress": read_progress(),
        "import_busy": job_is_running(),
    }


@router.get("/import", response_class=HTMLResponse)
def import_center(request: Request, session: Session = Depends(db_session)) -> HTMLResponse:
    runs = list(session.scalars(select(ImportRun).order_by(ImportRun.id.desc()).limit(20)).all())
    return templates.TemplateResponse(
        request,
        "import/index.html",
        {
            "notice": _notice(request),
            "fixtures": list_fixture_files(),
            "default_fixture": DEFAULT_FIXTURE.name,
            "runs": runs,
            "dev_mode": request.query_params.get("dev") == "1",
            **_nav(session),
        },
    )


@router.get("/import/progress", response_class=HTMLResponse)
def import_progress_fragment(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "import/progress.html",
        {"progress": read_progress(), "import_busy": job_is_running()},
    )


@router.get("/import/preview-result", response_class=HTMLResponse)
def import_preview_result(request: Request, session: Session = Depends(db_session)) -> HTMLResponse:
    payload = load_preview_page()
    if payload is None:
        return RedirectResponse("/import", status_code=HTTP_303_SEE_OTHER)
    result = _result_from_preview_payload(payload)
    level = normalize_level_filter(request.query_params.get("level"))
    filtered = [item for item in result.outcomes if item.level == level] if level else list(result.outcomes)
    shown = filtered[:PREVIEW_OUTCOME_LIMIT]
    level_counts = Counter(item.level for item in result.outcomes)
    return templates.TemplateResponse(
        request,
        "import/preview.html",
        {
            "result": result,
            "fixture_name": (payload.get("apply_hidden") or {}).get("fixture"),
            "apply_action": payload.get("apply_action") or "/import/apply",
            "apply_hidden": payload.get("apply_hidden") or {},
            "source_label": payload.get("source_label") or "",
            "without_gps": int(payload.get("without_gps") or 0),
            "notice": NOTICES["preview"],
            "level": level,
            "level_options": LEVEL_FILTER_OPTIONS,
            "level_counts": level_counts,
            "shown_outcomes": shown,
            "filtered_total": len(filtered),
            "preview_limit": PREVIEW_OUTCOME_LIMIT,
            **_nav(session),
        },
    )


@router.post("/import/preview")
async def import_preview(request: Request, background_tasks: BackgroundTasks):
    form = await request.form()
    path = _fixture_path(str(form.get("fixture") or ""))
    if not try_begin_job(source_type="fixture", message="Připravuji náhled…", kind="preview"):
        return RedirectResponse("/import?notice=already_running", status_code=HTTP_303_SEE_OTHER)
    background_tasks.add_task(run_fixture_preview, str(path))
    return RedirectResponse("/import?notice=preview_running", status_code=HTTP_303_SEE_OTHER)


@router.post("/import/apply")
async def import_apply(request: Request, background_tasks: BackgroundTasks):
    form = await request.form()
    path = _fixture_path(str(form.get("fixture") or ""))
    if not try_begin_job(source_type="fixture", message="Spouštím import…"):
        return RedirectResponse("/import?notice=already_running", status_code=HTTP_303_SEE_OTHER)
    background_tasks.add_task(run_fixture_apply, str(path))
    return RedirectResponse("/import?notice=import_running", status_code=HTTP_303_SEE_OTHER)


@router.post("/import/wikidata/preview")
async def wikidata_preview(request: Request, background_tasks: BackgroundTasks):
    return await _preview_named(request, background_tasks, "wikidata", "Spouštím náhled Wikidata…")


@router.post("/import/wikidata/apply")
async def wikidata_apply(request: Request, background_tasks: BackgroundTasks):
    form = await request.form()
    if not try_begin_job(source_type="wikidata", message="Spouštím import Wikidata…"):
        return RedirectResponse("/import?notice=already_running", status_code=HTTP_303_SEE_OTHER)
    background_tasks.add_task(run_named_apply, "wikidata", use_cache=_use_cache(form), public_ids=None)
    return RedirectResponse("/import?notice=import_running", status_code=HTTP_303_SEE_OTHER)


async def _apply_named(request: Request, background_tasks: BackgroundTasks, source_type: str, message: str):
    form = await request.form()
    if not try_begin_job(source_type=source_type, message=message):
        return RedirectResponse("/import?notice=already_running", status_code=HTTP_303_SEE_OTHER)
    public_ids = _public_ids_from_form(form) if source_type == "official_web" else None
    background_tasks.add_task(
        run_named_apply, source_type, use_cache=_use_cache(form), public_ids=public_ids
    )
    return RedirectResponse("/import?notice=import_running", status_code=HTTP_303_SEE_OTHER)


async def _preview_named(request: Request, background_tasks: BackgroundTasks, source_type: str, message: str):
    form = await request.form()
    if not try_begin_job(source_type=source_type, message=message, kind="preview"):
        return RedirectResponse("/import?notice=already_running", status_code=HTTP_303_SEE_OTHER)
    public_ids = _public_ids_from_form(form) if source_type == "official_web" else None
    background_tasks.add_task(
        run_named_preview, source_type, use_cache=_use_cache(form), public_ids=public_ids
    )
    return RedirectResponse("/import?notice=preview_running", status_code=HTTP_303_SEE_OTHER)


@router.post("/import/pamatkovy_katalog/preview")
async def katalog_preview(request: Request, background_tasks: BackgroundTasks):
    return await _preview_named(
        request, background_tasks, "pamatkovy_katalog", "Spouštím náhled Památkového katalogu…"
    )


@router.post("/import/pamatkovy_katalog/apply")
async def katalog_apply(request: Request, background_tasks: BackgroundTasks):
    return await _apply_named(request, background_tasks, "pamatkovy_katalog", "Spouštím import Památkového katalogu…")


@router.post("/import/ruian/preview")
async def ruian_preview(request: Request, background_tasks: BackgroundTasks):
    return await _preview_named(request, background_tasks, "ruian", "Spouštím náhled RÚIAN…")


@router.post("/import/ruian/apply")
async def ruian_apply(request: Request, background_tasks: BackgroundTasks):
    return await _apply_named(request, background_tasks, "ruian", "Spouštím normalizaci RÚIAN…")


@router.post("/import/npu/preview")
async def npu_preview(request: Request, background_tasks: BackgroundTasks):
    return await _preview_named(request, background_tasks, "npu", "Spouštím náhled NPÚ…")


@router.post("/import/npu/apply")
async def npu_apply(request: Request, background_tasks: BackgroundTasks):
    return await _apply_named(request, background_tasks, "npu", "Spouštím import NPÚ…")


@router.post("/import/wikimedia_commons/preview")
async def commons_preview(request: Request, background_tasks: BackgroundTasks):
    return await _preview_named(request, background_tasks, "wikimedia_commons", "Spouštím náhled Commons…")


@router.post("/import/wikimedia_commons/apply")
async def commons_apply(request: Request, background_tasks: BackgroundTasks):
    return await _apply_named(request, background_tasks, "wikimedia_commons", "Spouštím import Commons…")


@router.post("/import/wikipedia/preview")
async def wikipedia_preview(request: Request, background_tasks: BackgroundTasks):
    return await _preview_named(request, background_tasks, "wikipedia", "Spouštím náhled Wikipedia…")


@router.post("/import/wikipedia/apply")
async def wikipedia_apply(request: Request, background_tasks: BackgroundTasks):
    return await _apply_named(request, background_tasks, "wikipedia", "Spouštím import Wikipedia…")


@router.post("/import/osm/preview")
async def osm_preview(request: Request, background_tasks: BackgroundTasks):
    return await _preview_named(request, background_tasks, "osm", "Spouštím náhled OSM…")


@router.post("/import/osm/apply")
async def osm_apply(request: Request, background_tasks: BackgroundTasks):
    return await _apply_named(request, background_tasks, "osm", "Spouštím import OSM…")


@router.post("/import/official_web/preview")
async def official_web_preview(request: Request, background_tasks: BackgroundTasks):
    return await _preview_named(request, background_tasks, "official_web", "Spouštím náhled oficiálních webů…")


@router.post("/import/official_web/apply")
async def official_web_apply(request: Request, background_tasks: BackgroundTasks):
    return await _apply_named(request, background_tasks, "official_web", "Spouštím klasifikaci oficiálních webů…")


@router.get("/import/runs/{run_id}", response_class=HTMLResponse)
def import_run_detail(request: Request, run_id: int, session: Session = Depends(db_session)) -> HTMLResponse:
    run = session.get(ImportRun, run_id)
    if run is None:
        return templates.TemplateResponse(
            request,
            "places/not_found.html",
            {"public_id": str(run_id), **_nav(session)},
            status_code=HTTP_404_NOT_FOUND,
        )
    return templates.TemplateResponse(
        request,
        "import/run_detail.html",
        {"run": run, "notice": _notice(request), **_nav(session)},
    )


@router.get("/import/reviews", response_class=HTMLResponse)
def review_list(request: Request, session: Session = Depends(db_session)) -> HTMLResponse:
    status = request.query_params.get("status") or "open"
    stmt = select(ImportReview).order_by(ImportReview.id.desc())
    if status != "all":
        stmt = stmt.where(ImportReview.status == status)
    reviews = list(session.scalars(stmt).all())
    return templates.TemplateResponse(
        request,
        "import/review_list.html",
        {
            "reviews": reviews,
            "status": status,
            "notice": _notice(request),
            **_nav(session),
        },
    )


@router.post("/import/reviews/reprocess")
def review_reprocess(request: Request, background_tasks: BackgroundTasks):
    if job_is_running():
        return RedirectResponse("/import/reviews?notice=already_running", status_code=HTTP_303_SEE_OTHER)
    if not try_begin_job(source_type="review_reprocess", message="Přepočítávám frontu…", kind="apply"):
        return RedirectResponse("/import/reviews?notice=already_running", status_code=HTTP_303_SEE_OTHER)
    background_tasks.add_task(run_review_reprocess)
    return RedirectResponse("/import/reviews?notice=reprocess_running", status_code=HTTP_303_SEE_OTHER)


def _as_latlon(lat: object, lon: object) -> tuple[float, float] | None:
    try:
        lat_f = float(lat)  # type: ignore[arg-type]
        lon_f = float(lon)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    if not (math.isfinite(lat_f) and math.isfinite(lon_f)):
        return None
    if not (-90.0 <= lat_f <= 90.0 and -180.0 <= lon_f <= 180.0):
        return None
    return lat_f, lon_f


def _review_map_points(record: dict, review: ImportReview) -> list[dict]:
    points: list[dict] = []
    incoming = _as_latlon(record.get("latitude"), record.get("longitude"))
    if incoming is not None:
        points.append(
            {
                "lat": incoming[0],
                "lon": incoming[1],
                "label": str(record.get("name") or "Import"),
                "kind": "incoming",
            }
        )
    for candidate in review.candidates:
        place = candidate.place
        if place is None or not place.has_gps:
            continue
        coords = _as_latlon(place.latitude, place.longitude)
        if coords is None:
            continue
        points.append(
            {
                "lat": coords[0],
                "lon": coords[1],
                "label": place.name,
                "kind": "candidate",
            }
        )
    return points


@router.get("/import/reviews/{review_id}", response_class=HTMLResponse)
def review_detail(request: Request, review_id: int, session: Session = Depends(db_session)) -> HTMLResponse:
    review = session.get(ImportReview, review_id)
    if review is None:
        return templates.TemplateResponse(
            request,
            "places/not_found.html",
            {"public_id": str(review_id), **_nav(session)},
            status_code=HTTP_404_NOT_FOUND,
        )
    try:
        parsed = json.loads(review.raw_data)
    except json.JSONDecodeError:
        parsed = {}
    record = parsed if isinstance(parsed, dict) else {}
    points = _review_map_points(record, review)
    return templates.TemplateResponse(
        request,
        "import/review_detail.html",
        {
            "review": review,
            "record": record,
            "map_points_json": json.dumps(points, ensure_ascii=False).replace("</", "<\\/"),
            "notice": _notice(request),
            **_nav(session),
        },
    )


@router.post("/import/reviews/{review_id}/merge")
async def review_merge(request: Request, review_id: int, session: Session = Depends(db_session)):
    review = session.get(ImportReview, review_id)
    if review is None or review.status != "open":
        return RedirectResponse("/import/reviews", status_code=HTTP_303_SEE_OTHER)
    form = await request.form()
    place_id_raw = form.get("place_id") or review.candidate_place_id
    try:
        place_id = int(place_id_raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return RedirectResponse(f"/import/reviews/{review_id}", status_code=HTTP_303_SEE_OTHER)
    place = session.get(Place, place_id)
    if place is None:
        return RedirectResponse(f"/import/reviews/{review_id}", status_code=HTTP_303_SEE_OTHER)
    try:
        resolve_merge(session, review, place)
    except (RuntimeError, ValueError):
        _log.exception("review merge failed id=%s into place_id=%s", review_id, place.id)
        return RedirectResponse(
            f"/import/reviews/{review_id}?notice=merge_failed",
            status_code=HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(f"/places/{place.public_id}?notice=merged", status_code=HTTP_303_SEE_OTHER)


@router.post("/import/reviews/{review_id}/create")
def review_create(review_id: int, session: Session = Depends(db_session)):
    review = session.get(ImportReview, review_id)
    if review is None or review.status != "open":
        return RedirectResponse("/import/reviews", status_code=HTTP_303_SEE_OTHER)
    try:
        place = resolve_create_new(session, review)
    except (RuntimeError, ValueError):
        _log.exception("review create failed id=%s", review_id)
        return RedirectResponse(
            f"/import/reviews/{review_id}?notice=create_failed",
            status_code=HTTP_303_SEE_OTHER,
        )
    return RedirectResponse(f"/places/{place.public_id}?notice=created_new", status_code=HTTP_303_SEE_OTHER)


@router.post("/import/reviews/{review_id}/ignore")
def review_ignore(review_id: int, session: Session = Depends(db_session)):
    review = session.get(ImportReview, review_id)
    if review is None or review.status != "open":
        return RedirectResponse("/import/reviews", status_code=HTTP_303_SEE_OTHER)
    resolve_ignore(session, review)
    return RedirectResponse("/import/reviews?notice=ignored", status_code=HTTP_303_SEE_OTHER)


@router.post("/import/reviews/{review_id}/unignore")
def review_unignore(review_id: int, session: Session = Depends(db_session)):
    review = session.get(ImportReview, review_id)
    if review is None:
        return RedirectResponse("/import/reviews", status_code=HTTP_303_SEE_OTHER)
    unignore_review(session, review)
    return RedirectResponse(f"/import/reviews/{review_id}?notice=unignored", status_code=HTTP_303_SEE_OTHER)


@router.get("/import/changes", response_class=HTMLResponse)
def field_changes(request: Request, session: Session = Depends(db_session)) -> HTMLResponse:
    status = request.query_params.get("status") or "open"
    stmt = select(ImportFieldChange).order_by(ImportFieldChange.id.desc())
    if status != "all":
        stmt = stmt.where(ImportFieldChange.status == status)
    changes = list(session.scalars(stmt).all())
    return templates.TemplateResponse(
        request,
        "import/changes.html",
        {
            "changes": changes,
            "status": status,
            "notice": _notice(request),
            "decode_value": decode_value,
            **_nav(session),
        },
    )


@router.post("/import/changes/{change_id}/keep")
def change_keep(change_id: int, session: Session = Depends(db_session)):
    change = session.get(ImportFieldChange, change_id)
    if change is None or change.status != "open":
        return RedirectResponse("/import/changes", status_code=HTTP_303_SEE_OTHER)
    keep_master(session, change)
    session.commit()
    place = session.get(Place, change.place_id)
    target = f"/places/{place.public_id}?notice=keep_master" if place else "/import/changes?notice=keep_master"
    return RedirectResponse(target, status_code=HTTP_303_SEE_OTHER)


@router.post("/import/changes/{change_id}/take")
def change_take(change_id: int, session: Session = Depends(db_session)):
    change = session.get(ImportFieldChange, change_id)
    if change is None or change.status != "open":
        return RedirectResponse("/import/changes", status_code=HTTP_303_SEE_OTHER)
    take_source(session, change)
    session.commit()
    place = session.get(Place, change.place_id)
    target = f"/places/{place.public_id}?notice=take_source" if place else "/import/changes?notice=take_source"
    return RedirectResponse(target, status_code=HTTP_303_SEE_OTHER)


@router.get("/places/{public_id}/overrides", response_class=HTMLResponse)
def place_overrides(request: Request, public_id: str, session: Session = Depends(db_session)) -> HTMLResponse:
    place = get_place_by_public_id(session, public_id)
    if place is None:
        return templates.TemplateResponse(
            request,
            "places/not_found.html",
            {"public_id": public_id, **_nav(session)},
            status_code=HTTP_404_NOT_FOUND,
        )
    changes = list(
        session.scalars(
            select(ImportFieldChange)
            .where(ImportFieldChange.place_id == place.id)
            .order_by(ImportFieldChange.id.desc())
        ).all()
    )
    return templates.TemplateResponse(
        request,
        "places/overrides.html",
        {
            "place": place,
            "changes": changes,
            "notice": _notice(request),
            "decode_value": decode_value,
            **_nav(session),
        },
    )
