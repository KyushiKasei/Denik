import json
from io import BytesIO
from zipfile import ZIP_DEFLATED, ZIP_STORED, ZipFile

from app.services.diary_bundle import build_diary_zip, parse_diary_upload
from app.services.visit_photos import list_visit_photos, save_visit_photo


def test_parse_diary_zip_saves_photos(tmp_path, monkeypatch):
    from app import config

    monkeypatch.setenv("PAMATKY_DATA_DIR", str(tmp_path))
    config.ensure_data_dir()

    diary = {
        "schema_version": 2,
        "exported_at": "2026-08-17T12:00:00+02:00",
        "exported_from": "pwa",
        "place_states": [],
        "visits": [],
        "trips": [],
    }
    visit_id = "0198f23a-5e5e-7b31-a8be-8c99507a2140"
    photo_id = "0198f23a-5e5e-7b31-a8be-8c99507a2141"
    buffer = BytesIO()
    with ZipFile(buffer, "w") as archive:
        archive.writestr("diary.json", json.dumps(diary))
        archive.writestr(f"photos/{visit_id}/{photo_id}.jpg", b"\xff\xd8fake")
    data, count = parse_diary_upload(buffer.getvalue(), "diary.zip")
    assert data["schema_version"] == 2
    assert count == 1
    assert list_visit_photos(visit_id)


def test_parse_diary_zip_rejects_deflate() -> None:
    diary = {
        "schema_version": 2,
        "exported_at": "2026-08-17T12:00:00+02:00",
        "exported_from": "pwa",
        "place_states": [],
        "visits": [],
        "trips": [],
    }
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("diary.json", json.dumps(diary))
    try:
        parse_diary_upload(buffer.getvalue(), "diary.zip")
    except ValueError as exc:
        assert "bez komprese" in str(exc)
    else:
        raise AssertionError("očekáváno ValueError")


def test_build_diary_zip_includes_uuid_photos(tmp_path, monkeypatch):
    from app import config

    monkeypatch.setenv("PAMATKY_DATA_DIR", str(tmp_path))
    config.ensure_data_dir()
    visit_id = "0198f23a-5e5e-7b31-a8be-8c99507a2140"
    photo_id = "0198f23a-5e5e-7b31-a8be-8c99507a2141"
    save_visit_photo(visit_id, f"{photo_id}.jpg", b"\xff\xd8fake")
    diary = {
        "schema_version": 2,
        "exported_at": "2026-08-17T12:00:00+02:00",
        "exported_from": "pc",
        "place_states": [],
        "visits": [],
        "trips": [],
    }
    payload = build_diary_zip(diary)
    with ZipFile(BytesIO(payload)) as archive:
        names = archive.namelist()
        assert archive.getinfo("diary.json").compress_type == ZIP_STORED
    assert "diary.json" in names
    assert f"photos/{visit_id}/{photo_id}.jpg" in names


def test_parse_diary_zip_skips_extra_and_huge_photos(tmp_path, monkeypatch):
    from app import config
    from app.services import diary_bundle

    monkeypatch.setenv("PAMATKY_DATA_DIR", str(tmp_path))
    config.ensure_data_dir()
    monkeypatch.setattr(diary_bundle, "MAX_PHOTO_BYTES", 20)
    diary = {
        "schema_version": 2,
        "exported_at": "2026-08-17T12:00:00+02:00",
        "exported_from": "pwa",
        "place_states": [],
        "visits": [],
        "trips": [],
    }
    visit_id = "0198f23a-5e5e-7b31-a8be-8c99507a2140"
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_STORED) as archive:
        archive.writestr("diary.json", json.dumps(diary))
        for index in range(4):
            photo_id = f"0198f23a-5e5e-7b31-a8be-8c99507a214{index}"
            archive.writestr(f"photos/{visit_id}/{photo_id}.jpg", b"ok")
        archive.writestr(
            "photos/0198f23a-5e5e-7b31-a8be-8c99507a2150/0198f23a-5e5e-7b31-a8be-8c99507a2151.jpg",
            b"x" * 32,
        )
    _data, count = parse_diary_upload(buffer.getvalue(), "diary.zip")
    assert count == 3
    assert len(list_visit_photos(visit_id)) == 3
    assert list_visit_photos("0198f23a-5e5e-7b31-a8be-8c99507a2150") == []


def test_parse_diary_zip_rejects_huge_diary_json(monkeypatch) -> None:
    from app.services import diary_bundle

    monkeypatch.setattr(diary_bundle, "MAX_DIARY_JSON_BYTES", 10)
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_STORED) as archive:
        archive.writestr("diary.json", json.dumps({"schema_version": 2, "visits": []}))
    try:
        parse_diary_upload(buffer.getvalue(), "diary.zip")
    except ValueError as exc:
        assert "moc velký" in str(exc)
    else:
        raise AssertionError("očekáváno ValueError")


def test_parse_diary_json_rejects_huge(monkeypatch) -> None:
    from app.services import diary_bundle

    monkeypatch.setattr(diary_bundle, "MAX_DIARY_JSON_BYTES", 10)
    try:
        parse_diary_upload(b'{"visits":[]}', "diary.json")
    except ValueError as exc:
        assert "moc velký" in str(exc)
    else:
        raise AssertionError("očekáváno ValueError")


def test_save_visit_photo_rejects_fourth(tmp_path, monkeypatch):
    from app import config
    from app.services.visit_photos import MAX_PHOTOS_PER_VISIT, list_visit_photos, save_visit_photo

    monkeypatch.setenv("PAMATKY_DATA_DIR", str(tmp_path))
    config.ensure_data_dir()
    visit_id = "0198f23a-5e5e-7b31-a8be-8c99507a2140"
    for index in range(MAX_PHOTOS_PER_VISIT):
        save_visit_photo(visit_id, f"keep{index}.jpg", b"jpeg-bytes")
    try:
        save_visit_photo(visit_id, "extra.jpg", b"jpeg-bytes")
    except ValueError as exc:
        assert "nejvýš" in str(exc)
    else:
        raise AssertionError("očekáváno ValueError")
    assert len(list_visit_photos(visit_id)) == MAX_PHOTOS_PER_VISIT
    save_visit_photo(visit_id, "keep0.jpg", b"overwrite")
    assert len(list_visit_photos(visit_id)) == MAX_PHOTOS_PER_VISIT


def test_parse_diary_zip_invalid_schema_does_not_save_photos(tmp_path, monkeypatch):
    from app import config

    monkeypatch.setenv("PAMATKY_DATA_DIR", str(tmp_path))
    config.ensure_data_dir()
    visit_id = "0198f23a-5e5e-7b31-a8be-8c99507a2140"
    photo_id = "0198f23a-5e5e-7b31-a8be-8c99507a2141"
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_STORED) as archive:
        archive.writestr("diary.json", json.dumps({"schema_version": 2, "visits": []}))
        archive.writestr(f"photos/{visit_id}/{photo_id}.jpg", b"\xff\xd8fake")
    try:
        parse_diary_upload(buffer.getvalue(), "diary.zip")
    except ValueError as exc:
        assert "Nevalidní" in str(exc) or "schema" in str(exc).casefold()
    else:
        raise AssertionError("očekáváno ValueError")
    assert list_visit_photos(visit_id) == []


def test_build_diary_zip_skips_oversized_photos(tmp_path, monkeypatch):
    from app import config
    from app.services import diary_bundle, visit_photos

    monkeypatch.setenv("PAMATKY_DATA_DIR", str(tmp_path))
    config.ensure_data_dir()
    visit_id = "0198f23a-5e5e-7b31-a8be-8c99507a2140"
    keep_id = "0198f23a-5e5e-7b31-a8be-8c99507a2141"
    huge_id = "0198f23a-5e5e-7b31-a8be-8c99507a2142"
    save_visit_photo(visit_id, f"{keep_id}.jpg", b"\xff\xd8ok")
    huge = visit_photos.visit_photo_dir(visit_id) / f"{huge_id}.jpg"
    huge.write_bytes(b"x" * (diary_bundle.MAX_PHOTO_BYTES + 1))
    diary = {
        "schema_version": 2,
        "exported_at": "2026-08-17T12:00:00+02:00",
        "exported_from": "pc",
        "place_states": [],
        "visits": [],
        "trips": [],
    }
    payload = build_diary_zip(diary)
    with ZipFile(BytesIO(payload)) as archive:
        names = archive.namelist()
    assert f"photos/{visit_id}/{keep_id}.jpg" in names
    assert f"photos/{visit_id}/{huge_id}.jpg" not in names


def test_parse_diary_upload_rejects_huge_payload(monkeypatch) -> None:
    from app.services import diary_bundle

    monkeypatch.setattr(diary_bundle, "MAX_UPLOAD_BYTES", 10)
    try:
        parse_diary_upload(b"x" * 11, "diary.zip")
    except ValueError as exc:
        assert "80 MB" in str(exc) or "větší" in str(exc)
    else:
        raise AssertionError("očekáváno ValueError")
