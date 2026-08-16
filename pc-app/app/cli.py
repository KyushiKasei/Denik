"""Příkazová řádka PC aplikace: export catalog.json, deník a import zdrojů."""

from __future__ import annotations

import argparse
from pathlib import Path

from app.config import ensure_data_dir, get_database_path
from app.db.migrate import run_migrations
from app.db.seed import seed_place_types
from app.db.session import get_session
from app.importers.http_client import DownloadError
from app.importers.wikidata.client import SparqlError
from app.logging_setup import setup_logging
from app.services.apply_import import ImportApplyError, apply_import
from app.services.catalog_export import export_catalog
from app.services.diary_io import export_diary, import_diary
from app.services.diary_schema import load_and_validate_diary
from app.services.import_job import SOURCE_META, load_source_records


def _import_source(session, source: str, *, use_cache: bool) -> int:
    print(f"stahuji {source}{' (cache)' if use_cache else ''}…")
    try:
        records = load_source_records(session, source, use_cache=use_cache)
    except (SparqlError, DownloadError, ValueError) as exc:
        print(f"stažení {source} selhalo: {exc}")
        return 1
    print(f"zapisuji {len(records)} záznamů…")
    try:
        result = apply_import(session, records, source, make_backup=True)
    except ImportApplyError as exc:
        print(f"import selhal a byl vrácen zpět: {exc}")
        return 1
    print(
        f"{source}: {result.status} přijato={result.records_received} "
        f"+{result.records_created} ~{result.records_updated} "
        f"={result.records_unchanged} review={result.records_review} "
        f"ignored={result.records_ignored} failed={result.records_failed}"
    )
    if result.backup_path:
        print(f"záloha: {result.backup_path}")
    return 0 if result.status == "applied" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pamatky")
    sub = parser.add_subparsers(dest="command", required=True)
    export_cmd = sub.add_parser(
        "export-catalog",
        help="Exportovat catalog.json z master hodnot Place (bez archivovaných)",
    )
    export_cmd.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Cílová cesta. Výchozí: <data_dir>/export/catalog.json",
    )
    diary_export_cmd = sub.add_parser(
        "export-diary",
        help="Exportovat diary.json (návštěvy a osobní stavy, včetně soft-delete)",
    )
    diary_export_cmd.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Cílová cesta. Výchozí: <data_dir>/export/diary.json",
    )
    diary_import_cmd = sub.add_parser(
        "import-diary",
        help="Importovat diary.json (idempotentní sloučení, nevytváří Place)",
    )
    diary_import_cmd.add_argument("path", type=Path, help="Cesta k diary.json")
    source_import_cmd = sub.add_parser(
        "import-source",
        help="Importovat zdroj do katalogu (Wikidata, OSM, …) se zálohou",
    )
    source_import_cmd.add_argument(
        "source",
        choices=sorted(SOURCE_META),
        help="Zdroj: wikidata, wikipedia, osm, …",
    )
    source_import_cmd.add_argument(
        "--use-cache",
        action="store_true",
        help="Použít poslední staženou odpověď (bez sítě)",
    )
    args = parser.parse_args(argv)

    ensure_data_dir()
    setup_logging()
    run_migrations(get_database_path())
    session = get_session()
    try:
        seed_place_types(session)
        if args.command == "export-catalog":
            result = export_catalog(session, args.output)
            change = "změna obsahu" if result.content_changed else "beze změny obsahu"
            print(
                f"catalog.json schema 1, verze {result.catalog_version}, "
                f"{result.place_count} míst ({change}) → {result.path}"
            )
            return 0
        if args.command == "export-diary":
            result = export_diary(session, args.output)
            print(
                f"diary.json schema {result.diary['schema_version']}, {result.visit_count} návštěv, "
                f"{result.state_count} stavů, {len(result.diary.get('trips') or [])} výletů → {result.path}"
            )
            return 0
        if args.command == "import-diary":
            data = load_and_validate_diary(args.path)
            result = import_diary(session, data)
            print(
                f"deník: návštěvy +{result.visits_inserted} ~{result.visits_updated} "
                f"={result.visits_unchanged}; stavy +{result.states_inserted} "
                f"~{result.states_updated} ={result.states_unchanged}; "
                f"výlety +{result.trips_inserted} ~{result.trips_updated} ={result.trips_unchanged}"
            )
            if result.unknown_place_ids:
                print(f"neznámá place_id ({len(result.unknown_place_ids)}): Place nevytvořen")
            if result.backup_path:
                print(f"záloha: {result.backup_path}")
            return 0
        if args.command == "import-source":
            return _import_source(session, args.source, use_cache=args.use_cache)
    finally:
        session.close()
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
