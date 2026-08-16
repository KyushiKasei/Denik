from __future__ import annotations

import json
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import REPO_ROOT, get_default_catalog_path
from app.db.models import Place, PlacePhoto, PlaceSource
from app.importers.fixture import DEFAULT_FIXTURE, load_fixture
from app.services.apply_import import apply_import
from app.services.catalog_export import export_catalog, place_to_catalog_item
from app.services.catalog_schema import CatalogSchemaError, load_and_validate_catalog, validate_catalog
from app.services.places import PlaceInput, archive_place, create_place

SAMPLE_CATALOG = REPO_ROOT / "fixtures" / "catalog.sample.json"


def _place_input(**overrides) -> PlaceInput:
    data = PlaceInput(
        name="Bouzov",
        condition="PRESERVED",
        visitability="REGULAR",
        quality_status="VERIFIED",
        heritage_status="NKP",
        municipality="Bouzov",
        district="Olomouc",
        region="Olomoucký kraj",
        latitude=49.704,
        longitude=16.891,
        official_website="https://www.hrad-bouzov.cz/",
        wikipedia_url="https://cs.wikipedia.org/wiki/Bouzov_(hrad)",
        type_codes=["CASTLE"],
        alternative_names=["Hrad Bouzov", "Státní hrad Bouzov"],
        short_description="Gotický hrad ze 14. století.",
    )
    for key, value in overrides.items():
        setattr(data, key, value)
    return data


def _form_payload(**overrides) -> dict[str, str | list[str]]:
    data: dict[str, str | list[str]] = {
        "name": "Bouzov",
        "condition": "PRESERVED",
        "visitability": "REGULAR",
        "quality_status": "VERIFIED",
        "country": "CZ",
        "municipality": "Bouzov",
        "district": "Olomouc",
        "region": "Olomoucký kraj",
        "latitude": "49.704",
        "longitude": "16.891",
        "official_website": "https://www.hrad-bouzov.cz/",
        "type_codes": ["CASTLE"],
    }
    data.update(overrides)
    return data


def test_sample_catalog_matches_schema() -> None:
    catalog = load_and_validate_catalog(SAMPLE_CATALOG)
    assert catalog["schema_version"] == 1
    assert catalog["places"][0]["name"] == "Bouzov"
    assert isinstance(catalog["places"][0]["id"], str)


def test_export_validates_against_schema(session: Session, tmp_path: Path) -> None:
    place = create_place(session, _place_input())
    result = export_catalog(session, tmp_path / "catalog.json")
    validate_catalog(result.catalog)
    loaded = load_and_validate_catalog(result.path)
    assert loaded["schema_version"] == 1
    assert loaded["places"][0]["id"] == place.public_id
    assert loaded["places"][0]["unesco"] is False


def test_invalid_catalog_is_rejected(tmp_path: Path) -> None:
    sample = json.loads(SAMPLE_CATALOG.read_text(encoding="utf-8"))
    with pytest.raises(CatalogSchemaError, match="schema_version"):
        validate_catalog({**sample, "schema_version": 99})

    integer_id = json.loads(json.dumps(sample))
    integer_id["places"][0]["id"] = 1
    with pytest.raises(CatalogSchemaError):
        validate_catalog(integer_id)

    broken = tmp_path / "bad.json"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(CatalogSchemaError, match="JSON"):
        load_and_validate_catalog(broken)

    with pytest.raises(CatalogSchemaError, match="objekt"):
        validate_catalog(["not", "an", "object"])

    duplicate = json.loads(json.dumps(sample))
    duplicate["places"].append(duplicate["places"][0])
    with pytest.raises(CatalogSchemaError, match="Duplicitní"):
        validate_catalog(duplicate)


def test_json_id_is_public_id_not_integer_pk(session: Session, tmp_path: Path) -> None:
    place = create_place(session, _place_input())
    result = export_catalog(session, tmp_path / "catalog.json")
    item = result.catalog["places"][0]
    assert item["id"] == place.public_id
    assert item["id"] != str(place.id)
    assert isinstance(item["id"], str)
    assert isinstance(place.id, int)
    raw = json.dumps(result.catalog)
    assert f'"id": {place.id}' not in raw
    assert f'"id":{place.id}' not in raw
    assert "quality_status" not in item
    assert "archived_at" not in item
    assert "public_id" not in item


def test_archived_place_is_not_exported(session: Session, tmp_path: Path) -> None:
    active = create_place(session, _place_input())
    archived = create_place(session, _place_input(name="Zaniklý hrad"))
    archive_place(session, archived)
    result = export_catalog(session, tmp_path / "catalog.json")
    ids = {item["id"] for item in result.catalog["places"]}
    assert active.public_id in ids
    assert archived.public_id not in ids
    still = session.scalar(select(Place).where(Place.public_id == archived.public_id))
    assert still is not None
    assert still.archived_at is not None
    assert still.public_id == archived.public_id


def test_catalog_version_increments_only_on_content_change(session: Session, tmp_path: Path) -> None:
    place = create_place(session, _place_input())
    first = export_catalog(session, tmp_path / "v1.json")
    second = export_catalog(session, tmp_path / "v1b.json")
    assert first.catalog_version == 1
    assert first.content_changed is True
    assert second.catalog_version == first.catalog_version
    assert second.content_changed is False
    assert second.content_hash == first.content_hash

    place.name = "Hrad Bouzov"
    session.commit()
    third = export_catalog(session, tmp_path / "v2.json")
    assert third.catalog_version == first.catalog_version + 1
    assert third.content_changed is True
    assert third.content_hash != first.content_hash


def test_export_bouzov_keeps_public_id_after_repeated_import(session: Session, tmp_path: Path) -> None:
    source_type, records = load_fixture(DEFAULT_FIXTURE)
    apply_import(session, records, source_type, make_backup=False)
    bouzov = session.scalar(select(Place).where(Place.name == "Bouzov"))
    assert bouzov is not None
    public_id = bouzov.public_id
    apply_import(session, records, source_type, make_backup=False)
    result = export_catalog(session, tmp_path / "catalog.json")
    exported = next(item for item in result.catalog["places"] if item["name"] == "Bouzov")
    assert exported["id"] == public_id
    assert exported["links"]["wikidata"] == "https://www.wikidata.org/wiki/Q122922"
    validate_catalog(result.catalog)


def test_image_and_missing_gps_export(session: Session, tmp_path: Path) -> None:
    place = create_place(
        session,
        _place_input(latitude=None, longitude=None, official_website=None),
    )
    session.add(
        PlacePhoto(
            place_id=place.id,
            source="wikimedia_commons",
            thumbnail_url="https://commons.wikimedia.org/wiki/Special:FilePath/Hrad_Bouzov.jpg?width=640",
            original_url="https://commons.wikimedia.org/wiki/File:Hrad_Bouzov.jpg",
            attribution="Jan Novák / Wikimedia Commons",
            license="CC BY-SA 4.0",
            license_url="https://creativecommons.org/licenses/by-sa/4.0/",
            is_primary=1,
        )
    )
    session.add(
        PlaceSource(
            place_id=place.id,
            source_type="wikidata",
            external_id="Q122922",
            created_at="2026-08-14T20:00:00+02:00",
            updated_at="2026-08-14T20:00:00+02:00",
        )
    )
    session.commit()
    session.refresh(place)
    item = place_to_catalog_item(place)
    assert item["location"]["latitude"] is None
    assert item["location"]["longitude"] is None
    assert item["image"] is not None
    assert item["image"]["license"] == "CC BY-SA 4.0"
    assert item["links"]["wikidata"] == "https://www.wikidata.org/wiki/Q122922"
    result = export_catalog(session, tmp_path / "catalog.json")
    validate_catalog(result.catalog)


def test_ui_has_export_button_and_downloads_catalog(client) -> None:
    created = client.post("/places", data=_form_payload(), follow_redirects=False)
    assert created.status_code == 303
    dashboard = client.get("/")
    assert dashboard.status_code == 200
    assert "Exportovat catalog.json" in dashboard.text
    listing = client.get("/places")
    assert "Exportovat catalog.json" in listing.text

    response = client.post("/catalog/export")
    assert response.status_code == 200
    assert "catalog.json" in response.headers.get("content-disposition", "")
    data = response.json()
    validate_catalog(data)
    assert data["places"][0]["name"] == "Bouzov"
    assert isinstance(data["places"][0]["id"], str)
    saved = get_default_catalog_path()
    assert saved.is_file()
    assert load_and_validate_catalog(saved)["catalog_version"] == data["catalog_version"]


def test_cli_export_catalog(client, tmp_path: Path) -> None:
    client.post("/places", data=_form_payload())
    from app.cli import main

    out = tmp_path / "from-cli.json"
    assert main(["export-catalog", "-o", str(out)]) == 0
    catalog = load_and_validate_catalog(out)
    assert catalog["places"][0]["name"] == "Bouzov"
    assert isinstance(catalog["places"][0]["id"], str)


def test_cli_import_source_wikidata(client, monkeypatch) -> None:
    from sqlalchemy import func, select

    from app.cli import main
    from app.db.models import Place
    from app.db.session import get_session
    from app.importers.wikidata.importer import SAMPLE_SPARQL_FIXTURE, records_from_file

    records = records_from_file(SAMPLE_SPARQL_FIXTURE, fetched_at="t")
    monkeypatch.setattr("app.cli.load_source_records", lambda _session, _source, use_cache=False: records)
    assert main(["import-source", "wikidata"]) == 0
    session = get_session()
    try:
        assert session.scalar(select(func.count()).select_from(Place)) == 6
        assert session.scalar(select(Place).where(Place.name == "Bouzov")) is not None
    finally:
        session.close()
