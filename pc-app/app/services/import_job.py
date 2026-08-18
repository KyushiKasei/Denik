"""Import na pozadí, aby šlo v UI číst průběh kolik z kolika."""

from __future__ import annotations

import threading
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.session import get_session
from app.importers.fixture import load_fixture
from app.importers.http_client import DownloadError
from app.importers.npu.importer import fetch_npu_records
from app.importers.official_web.importer import fetch_official_web_records
from app.importers.osm.importer import fetch_osm_records
from app.importers.pamatkovy_katalog.importer import fetch_pamatkovy_katalog_records
from app.importers.pamatkovy_katalog.parser import fetch_summary as katalog_summary
from app.importers.ruian.importer import fetch_ruian_records
from app.importers.wikidata.client import SparqlError
from app.importers.wikidata.importer import fetch_summary, fetch_wikidata_records
from app.importers.wikimedia_commons.importer import fetch_commons_records
from app.importers.wikipedia.importer import fetch_wikipedia_records
from app.services.apply_import import (
    ImportApplyError,
    apply_import,
    existing_external_ids,
    preview_import,
    record_failed_run,
    reprocess_open_reviews,
)
from app.services.import_progress import save_preview_page, write_progress

_job_lock = threading.Lock()
_job_running = False


def job_is_running() -> bool:
    with _job_lock:
        return _job_running


SOURCE_META: dict[str, tuple[str, str]] = {
    "wikidata": ("Wikidata SPARQL", "/import/wikidata/apply"),
    "pamatkovy_katalog": ("Památkový katalog CSV", "/import/pamatkovy_katalog/apply"),
    "ruian": ("RÚIAN číselníky", "/import/ruian/apply"),
    "npu": ("NPÚ spravované objekty", "/import/npu/apply"),
    "wikimedia_commons": ("Wikimedia Commons metadata", "/import/wikimedia_commons/apply"),
    "wikipedia": ("Wikipedia URL / úplnost", "/import/wikipedia/apply"),
    "osm": ("OpenStreetMap (volitelný doplněk)", "/import/osm/apply"),
    "official_web": ("Přístupnost z oficiálních webů", "/import/official_web/apply"),
}


def try_begin_job(*, source_type: str, message: str, kind: str = "apply") -> bool:
    global _job_running
    with _job_lock:
        if _job_running:
            return False
        _job_running = True
        write_progress(
            status="running",
            phase="fetch",
            source_type=source_type,
            kind=kind,
            current=0,
            total=0,
            created=0,
            updated=0,
            unchanged=0,
            review=0,
            failed=0,
            ignored=0,
            current_name="",
            message=message,
            run_id=0,
            force=True,
        )
        return True


def _end_job() -> None:
    global _job_running
    with _job_lock:
        _job_running = False


def reset_job_state() -> None:
    """Pro testy: uvolní zámek po selhání běhu."""
    _end_job()


def load_source_records(
    session: Session,
    source_type: str,
    *,
    use_cache: bool,
    public_ids: list[str] | None = None,
):
    if source_type == "wikidata":
        return fetch_wikidata_records(use_cache=use_cache, session=session)
    if source_type == "pamatkovy_katalog":
        return fetch_pamatkovy_katalog_records(
            use_cache=use_cache,
            known_uskp=existing_external_ids(session, "uskp"),
            known_catalog=existing_external_ids(session, "pamatkovy_katalog"),
        )
    if source_type == "ruian":
        def on_progress(current: int, total: int, name: str) -> None:
            write_progress(
                phase="fetch",
                current=current,
                total=total,
                current_name=name,
                message=f"Obec ze souřadnic: {current} / {total}",
            )

        return fetch_ruian_records(session, use_cache=use_cache, on_progress=on_progress)
    if source_type == "npu":
        return fetch_npu_records(use_cache=use_cache)
    if source_type == "wikimedia_commons":
        return fetch_commons_records(session, use_cache=use_cache)
    if source_type == "wikipedia":
        return fetch_wikipedia_records(use_cache=use_cache)
    if source_type == "osm":
        return fetch_osm_records(use_cache=use_cache)
    if source_type == "official_web":
        return fetch_official_web_records(session, use_cache=use_cache, public_ids=public_ids)
    raise ValueError(f"Neznámý zdroj importu: {source_type}")


def _extra_log(source_type: str, records) -> str | None:
    if source_type == "wikidata":
        return fetch_summary(records)
    if source_type == "pamatkovy_katalog":
        return katalog_summary(records)
    return None


def _without_gps(records) -> int:
    return sum(1 for item in records if item.latitude is None or item.longitude is None)


def run_fixture_preview(path: str) -> None:
    session = get_session()
    try:
        source_type, records = load_fixture(Path(path))
        write_progress(
            source_type=source_type,
            kind="preview",
            phase="match",
            total=len(records),
            message=f"Náhled 0 / {len(records)}",
            force=True,
        )
        result = preview_import(session, records, source_type)
        save_preview_page(
            source_label=f"fixture {Path(path).name}",
            apply_action="/import/apply",
            apply_hidden={"fixture": Path(path).name},
            without_gps=_without_gps(records),
            result=result,
        )
    except Exception as exc:
        record_failed_run(session, "fixture", str(exc))
        write_progress(status="failed", phase="error", message=str(exc), force=True)
    finally:
        session.close()
        _end_job()


def run_named_preview(source_type: str, *, use_cache: bool, public_ids: list[str] | None = None) -> None:
    session = get_session()
    label, apply_action = SOURCE_META.get(source_type, (source_type, "/import"))
    try:
        write_progress(
            source_type=source_type,
            kind="preview",
            phase="fetch",
            message="Stahuji zdroj…",
            force=True,
        )
        records = load_source_records(session, source_type, use_cache=use_cache, public_ids=public_ids)
        write_progress(
            phase="match",
            total=len(records),
            current=0,
            message=f"Náhled 0 / {len(records)}",
            force=True,
        )
        result = preview_import(
            session,
            records,
            source_type,
            extra_log=_extra_log(source_type, records),
        )
        hidden = {"use_cache": "1"}
        if public_ids:
            hidden["public_ids"] = "\n".join(public_ids)
        save_preview_page(
            source_label=label,
            apply_action=apply_action,
            apply_hidden=hidden,
            without_gps=_without_gps(records),
            result=result,
        )
    except (SparqlError, DownloadError, ValueError):
        record_failed_run(session, source_type, "Stažení zdroje selhalo.")
        write_progress(
            status="failed",
            phase="error",
            message="Stažení zdroje selhalo. Katalog se nezměnil.",
            force=True,
        )
    except Exception as exc:
        record_failed_run(session, source_type, str(exc))
        write_progress(status="failed", phase="error", message=str(exc), force=True)
    finally:
        session.close()
        _end_job()


def run_fixture_apply(path: str) -> None:
    session = get_session()
    try:
        source_type, records = load_fixture(Path(path))
        write_progress(
            source_type=source_type,
            phase="write",
            total=len(records),
            message=f"Zapisuji 0 / {len(records)}",
            force=True,
        )
        apply_import(session, records, source_type, make_backup=True)
    except ImportApplyError:
        write_progress(status="rolled_back", phase="error", message="Import selhal a byl vrácen zpět.", force=True)
    except Exception as exc:
        record_failed_run(session, "fixture", str(exc))
        write_progress(status="failed", phase="error", message=str(exc), force=True)
    finally:
        session.close()
        _end_job()


def run_named_apply(source_type: str, *, use_cache: bool, public_ids: list[str] | None = None) -> None:
    session = get_session()
    try:
        write_progress(
            source_type=source_type,
            phase="fetch",
            message="Stahuji zdroj…",
            force=True,
        )
        records = load_source_records(session, source_type, use_cache=use_cache, public_ids=public_ids)
        write_progress(
            phase="write",
            total=len(records),
            current=0,
            message=f"Zapisuji 0 / {len(records)}",
            force=True,
        )
        apply_import(
            session,
            records,
            source_type,
            make_backup=True,
            extra_log=_extra_log(source_type, records),
        )
    except (SparqlError, DownloadError, ValueError) as exc:
        record_failed_run(session, source_type, str(exc))
        write_progress(
            status="failed",
            phase="error",
            message="Stažení zdroje selhalo. Katalog se nezměnil.",
            force=True,
        )
    except ImportApplyError:
        write_progress(status="rolled_back", phase="error", message="Import selhal a byl vrácen zpět.", force=True)
    except Exception as exc:
        record_failed_run(session, source_type, str(exc))
        write_progress(status="failed", phase="error", message=str(exc), force=True)
    finally:
        session.close()
        _end_job()


def run_review_reprocess() -> None:
    session = get_session()
    try:
        write_progress(
            source_type="review_reprocess",
            phase="write",
            kind="apply",
            message="Přepočítávám frontu…",
            force=True,
        )
        reprocess_open_reviews(session, make_backup=True)
    except ImportApplyError:
        write_progress(
            status="rolled_back",
            phase="error",
            message="Přepočet fronty selhal a byl vrácen zpět.",
            force=True,
        )
    except Exception as exc:
        record_failed_run(session, "review_reprocess", str(exc))
        write_progress(status="failed", phase="error", message=str(exc), force=True)
    finally:
        session.close()
        _end_job()
