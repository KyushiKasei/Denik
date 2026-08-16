from __future__ import annotations

import re
from app.config import get_database_path
from app.services.backup import list_backups


def _create_place(client, name: str) -> str:
    created = client.post(
        "/places",
        data={
            "name": name,
            "condition": "PRESERVED",
            "visitability": "REGULAR",
            "quality_status": "VERIFIED",
            "country": "CZ",
            "type_codes": ["CASTLE"],
        },
        follow_redirects=False,
    )
    assert created.status_code == 303
    return created.headers["location"].split("/")[2].split("?")[0]


def test_backup_page_and_manual_backup(client) -> None:
    dashboard = client.get("/")
    assert dashboard.status_code == 200
    assert "Záloha a obnova" in dashboard.text

    page = client.get("/backup")
    assert page.status_code == 200
    assert "Vytvořit zálohu teď" in page.text
    assert "Obnovit z souboru" in page.text

    created = client.post("/backup/create", follow_redirects=True)
    assert created.status_code == 200
    assert "Záloha SQLite je hotová" in created.text
    backups = list_backups(get_database_path())
    assert len(backups) == 1
    assert "manual" in backups[0].name
    assert backups[0].name in created.text


def test_restore_from_listed_backup_replaces_catalog(client) -> None:
    first_id = _create_place(client, "Bouzov")
    created = client.post("/backup/create", follow_redirects=True)
    match = re.search(r'name="filename" value="([^"]+)"', created.text)
    assert match is not None
    filename = match.group(1)

    second_id = _create_place(client, "Karlštejn")
    listing = client.get("/places")
    assert "Bouzov" in listing.text
    assert "Karlštejn" in listing.text

    restored = client.post("/backup/restore", data={"filename": filename}, follow_redirects=True)
    assert restored.status_code == 200
    assert "obnovena ze zálohy" in restored.text.lower()

    listing_after = client.get("/places")
    assert "Bouzov" in listing_after.text
    assert "Karlštejn" not in listing_after.text
    assert first_id in client.get(f"/places/{first_id}").text
    missing = client.get(f"/places/{second_id}")
    assert missing.status_code == 404


def test_restore_upload_rejects_non_sqlite(client) -> None:
    response = client.post(
        "/backup/restore-upload",
        files={"file": ("not-db.txt", b"not a database", "text/plain")},
    )
    assert response.status_code == 400
    assert "SQLite" in response.text


def test_restore_upload_roundtrip(client) -> None:
    _create_place(client, "Bouzov")
    client.post("/backup/create")
    backups = list_backups(get_database_path())
    payload = backups[0].path.read_bytes()

    _create_place(client, "Bečov")
    restored = client.post(
        "/backup/restore-upload",
        files={"file": ("copy.sqlite3", payload, "application/vnd.sqlite3")},
        follow_redirects=True,
    )
    assert restored.status_code == 200
    listing = client.get("/places")
    assert "Bouzov" in listing.text
    assert "Bečov" not in listing.text
