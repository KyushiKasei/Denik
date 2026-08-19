from pathlib import Path

from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select

from app.db.enums import format_types, label
from app.services.diary_present import format_visit_date
from app.services.display import (
    display_place_name,
    explain_match_reason,
    format_distance_m,
    incoming_is_sparse,
    incoming_review_label,
    identity_conflicts,
)
from app.services.source_urls import identity_source_url, is_http_url, photo_display_url, source_page_url
from app.services.stamp_art import place_stamp_svg, stamp_svg, visit_stamp_svg

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"

MATCH_LEVEL_LABELS = {
    "MATCHED_EXACT": "Přesná shoda",
    "MATCHED_PROBABLE": "Pravděpodobná shoda",
    "IMPORT_REVIEW": "K rozhodnutí",
    "NEW_PLACE": "Nové místo",
    "IGNORED": "Ignorováno",
    "FAILED": "Chyba",
}

IMPORT_ACTION_LABELS = {
    "update": "Aktualizace",
    "create": "Nové místo",
    "review": "K rozhodnutí",
    "ignore": "Ignorovat",
    "fail": "Chyba",
}

REVIEW_STATUS_LABELS = {
    "open": "Otevřené",
    "ignored": "Ignorované",
    "merged": "Sloučeno",
    "created": "Vytvořeno jako nové",
    "resolved": "Vyřešeno",
}

RUN_STATUS_LABELS = {
    "running": "Běží",
    "completed": "Hotovo",
    "failed": "Selhalo",
    "rolled_back": "Vráceno",
}

CHANGE_STATUS_LABELS = {
    "open": "Otevřené",
    "kept": "Ponecháno master",
    "taken": "Převzato ze zdroje",
}


def with_count(name: str, counts: object = None, code: str = "") -> str:
    if not isinstance(counts, dict):
        return name
    try:
        return f"{name} ({int(counts.get(code, 0))})"
    except Exception:
        return name


def import_code_label(kind: str, code: str | None) -> str:
    if not code:
        return "—"
    tables = {
        "level": MATCH_LEVEL_LABELS,
        "action": IMPORT_ACTION_LABELS,
        "review_status": REVIEW_STATUS_LABELS,
        "run_status": RUN_STATUS_LABELS,
        "change_status": CHANGE_STATUS_LABELS,
    }
    return tables.get(kind, {}).get(code, code)


def count_open_reviews() -> int:
    from app.db.models import ImportReview
    from app.db.session import get_session

    try:
        session = get_session()
    except Exception:
        return 0
    try:
        return session.scalar(select(func.count()).select_from(ImportReview).where(ImportReview.status == "open")) or 0
    except Exception:
        return 0
    finally:
        session.close()


class NavAwareTemplates(Jinja2Templates):
    def TemplateResponse(self, request, name: str, context: dict | None = None, **kwargs):
        ctx = dict(context or {})
        if "open_review_count" not in ctx:
            ctx["open_review_count"] = count_open_reviews()
        return super().TemplateResponse(request, name, ctx, **kwargs)


templates = NavAwareTemplates(directory=str(TEMPLATES_DIR))
templates.env.globals["enum_label"] = label
templates.env.globals["is_http_url"] = is_http_url
templates.env.globals["photo_display_url"] = photo_display_url
templates.env.globals["source_page_url"] = source_page_url
templates.env.globals["import_code_label"] = import_code_label
templates.env.globals["with_count"] = with_count
templates.env.globals["stamp_svg"] = stamp_svg
templates.env.globals["visit_stamp_svg"] = visit_stamp_svg
templates.env.globals["place_stamp_svg"] = place_stamp_svg
templates.env.globals["format_visit_date"] = format_visit_date
templates.env.globals["display_place_name"] = display_place_name
templates.env.filters["display_place_name"] = display_place_name
templates.env.globals["explain_match_reason"] = explain_match_reason
templates.env.globals["incoming_review_label"] = incoming_review_label
templates.env.globals["format_distance_m"] = format_distance_m
templates.env.globals["incoming_is_sparse"] = incoming_is_sparse
templates.env.globals["identity_conflicts"] = identity_conflicts
templates.env.globals["format_types"] = format_types
templates.env.globals["identity_source_url"] = identity_source_url
