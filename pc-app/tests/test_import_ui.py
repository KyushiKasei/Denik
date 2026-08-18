from __future__ import annotations

import json

from sqlalchemy import select

from app.db.models import ImportReview, ImportRun, Place, PlaceSource
from app.db.session import get_session
from app.importers.base import CanonicalRecord
from app.importers.fixture import DEFAULT_FIXTURE
from app.importers.wikidata.importer import SAMPLE_SPARQL_FIXTURE, records_from_file
from app.services.apply_import import apply_import


def test_import_center_page(client) -> None:
    response = client.get("/import")
    assert response.status_code == 200
    assert "Import centrum" in response.text
    assert "small_dataset.json" in response.text
    assert "Náhled" in response.text
    assert "Aplikovat" in response.text
    assert "Wikidata" in response.text
    assert "Náhled Wikidata" in response.text
    assert "Památkový katalog" in response.text
    assert "RÚIAN" in response.text
    assert "NPÚ spravované" in response.text
    assert "Wikimedia Commons" in response.text
    assert "Wikipedia" in response.text
    assert "OpenStreetMap" in response.text
    assert "Doplňky zdrojů" in response.text
    assert "Přístupnost z oficiálních webů" in response.text
    assert "Vývoj" in response.text
    assert "<summary>Vývoj</summary>" in response.text
    assert "<details" in response.text
    assert "<details open" not in response.text

    dev = client.get("/import?dev=1")
    assert dev.status_code == 200
    assert "<details open" in dev.text


def test_import_buttons_disabled_when_job_running(client) -> None:
    from app.services.import_job import reset_job_state, try_begin_job

    assert try_begin_job(source_type="wikidata", message="test")
    try:
        page = client.get("/import")
        assert page.status_code == 200
        for action in (
            "/import/ruian/apply",
            "/import/npu/apply",
            "/import/wikimedia_commons/apply",
            "/import/wikipedia/apply",
            "/import/osm/apply",
            "/import/official_web/apply",
        ):
            assert f'formaction="{action}"' in page.text
            snippet = page.text.split(f'formaction="{action}"', 1)[1][:80]
            assert "disabled" in snippet
    finally:
        reset_job_state()


def test_preview_and_apply_via_ui(client) -> None:
    preview = client.post("/import/preview", data={"fixture": DEFAULT_FIXTURE.name}, follow_redirects=True)
    assert preview.status_code == 200
    assert "Náhled je hotový" in preview.text or "Zobrazit náhled" in preview.text
    result_page = client.get("/import/preview-result")
    assert result_page.status_code == 200
    assert "Náhled importu" in result_page.text
    assert "Přesná shoda" in result_page.text or "Nové místo" in result_page.text

    session = get_session()
    try:
        assert session.scalar(select(Place)) is None
    finally:
        session.close()

    applied = client.post("/import/apply", data={"fixture": DEFAULT_FIXTURE.name}, follow_redirects=True)
    assert applied.status_code == 200
    assert "Import byl zapsán" in applied.text

    session = get_session()
    try:
        assert session.scalar(select(Place)) is not None
    finally:
        session.close()


def test_review_queue_merge_create_ignore_buttons(client) -> None:
    client.post("/import/apply", data={"fixture": DEFAULT_FIXTURE.name})
    client.post("/import/apply", data={"fixture": "small_dataset_update.json"})
    listing = client.get("/import/reviews")
    assert listing.status_code == 200
    assert "Fronta k rozhodnutí" in listing.text
    assert "Karlstein" in listing.text or "Q-unclear-karlstein" in listing.text

    session = get_session()
    try:
        review = session.scalar(select(ImportReview).where(ImportReview.status == "open"))
        assert review is not None
        review_id = review.id
    finally:
        session.close()

    detail = client.get(f"/import/reviews/{review_id}")
    assert detail.status_code == 200
    assert "Sloučit" in detail.text
    assert "Vytvořit jako nové" in detail.text
    assert "Ignorovat" in detail.text
    assert "Otevřené" in detail.text or "otevřen" in detail.text.lower()
    home = client.get("/")
    assert home.status_code == 200
    assert 'class="badge"' in home.text

    ignored = client.post(f"/import/reviews/{review_id}/ignore", follow_redirects=True)
    assert ignored.status_code == 200
    assert "ignorovaná" in ignored.text.lower() or "Ignorovat" in ignored.text


def test_review_reprocess_merges_osm_centroid(client) -> None:
    session = get_session()
    try:
        apply_import(
            session,
            [
                CanonicalRecord.from_dict(
                    {
                        "source_type": "wikidata",
                        "external_id": "Q-pernstejn",
                        "external_ids": {"wikidata": "Q-pernstejn"},
                        "name": "Pernštejn",
                        "types": ["CASTLE"],
                        "municipality": "Nedvědice",
                        "latitude": 49.4508333333,
                        "longitude": 16.3188888888,
                        "fetched_at": "2026-08-16T21:00:00+02:00",
                    }
                )
            ],
            "wikidata",
            make_backup=True,
        )
        leftover = CanonicalRecord.from_dict(
            {
                "source_type": "osm",
                "external_id": "relation/10843713",
                "external_ids": {"osm": "relation/10843713"},
                "name": "Pernštejn",
                "types": ["CASTLE"],
                "latitude": 49.4513905,
                "longitude": 16.3172329,
                "fetched_at": "2026-08-16T21:00:00+02:00",
            }
        )
        import_run = session.scalar(select(ImportRun).order_by(ImportRun.id.desc()))
        assert import_run is not None
        session.add(
            ImportReview(
                import_run_id=import_run.id,
                source_type="osm",
                external_id="relation/10843713",
                raw_data=json.dumps(leftover.to_dict(), ensure_ascii=False),
                status="open",
                match_reason="C1 distance=134.8m similarity=1.000",
            )
        )
        session.commit()
    finally:
        session.close()

    listing = client.get("/import/reviews")
    assert listing.status_code == 200
    assert "Přepočítat frontu" in listing.text
    assert "relation/10843713" in listing.text

    done = client.post("/import/reviews/reprocess", follow_redirects=True)
    assert done.status_code == 200

    session = get_session()
    try:
        still_open = session.scalar(
            select(ImportReview).where(
                ImportReview.status == "open",
                ImportReview.external_id == "relation/10843713",
            )
        )
        assert still_open is None
        source = session.scalar(
            select(PlaceSource).where(PlaceSource.external_id == "relation/10843713")
        )
        assert source is not None
    finally:
        session.close()


def test_catalog_merge_two_bouzovs(client) -> None:
    client.post("/places", data={"name": "Bouzov", "condition": "UNKNOWN", "visitability": "UNKNOWN", "quality_status": "VERIFIED"})
    client.post(
        "/places",
        data={
            "name": "Hrad Bouzov",
            "condition": "PRESERVED",
            "visitability": "REGULAR",
            "quality_status": "PROBABLE",
            "municipality": "Bouzov",
            "latitude": "49.704",
            "longitude": "16.891",
        },
    )
    session = get_session()
    try:
        places = list(session.scalars(select(Place).order_by(Place.id)).all())
        assert len(places) == 2
        winner, loser = places[0], places[1]
        winner_id, loser_id = winner.public_id, loser.public_id
    finally:
        session.close()

    page = client.get(f"/places/{winner_id}/merge")
    assert page.status_code == 200
    assert "Sloučit sem" in page.text
    assert loser_id in page.text

    merged = client.post(
        f"/places/{winner_id}/merge",
        data={"loser_public_id": loser_id},
        follow_redirects=True,
    )
    assert merged.status_code == 200
    assert "sloučena" in merged.text.lower()
    assert winner_id in merged.text

    session = get_session()
    try:
        winner = session.scalar(select(Place).where(Place.public_id == winner_id))
        loser = session.scalar(select(Place).where(Place.public_id == loser_id))
        assert winner is not None
        assert loser is not None
        assert winner.archived_at is None
        assert loser.archived_at is not None
        assert loser.merged_into_public_id == winner_id
        assert winner.latitude == 49.704
    finally:
        session.close()


def test_wikidata_preview_and_apply_via_ui(client, monkeypatch) -> None:
    records = records_from_file(SAMPLE_SPARQL_FIXTURE)

    monkeypatch.setattr(
        "app.services.import_job.fetch_wikidata_records",
        lambda use_cache=False, session=None: records,
    )

    preview = client.post("/import/wikidata/preview", follow_redirects=True)
    assert preview.status_code == 200
    result_page = client.get("/import/preview-result")
    assert result_page.status_code == 200
    assert "Náhled importu" in result_page.text
    assert "Wikidata SPARQL" in result_page.text
    assert "Bez GPS" in result_page.text
    assert "Nové místo" in result_page.text

    session = get_session()
    try:
        assert session.scalar(select(Place)) is None
    finally:
        session.close()

    applied = client.post("/import/wikidata/apply", data={"use_cache": "1"}, follow_redirects=True)
    assert applied.status_code == 200
    assert "Import byl zapsán" in applied.text

    session = get_session()
    try:
        places = list(session.scalars(select(Place)).all())
        assert len(places) == 6
        qids = {
            source.external_id
            for place in places
            for source in place.sources
            if source.source_type == "wikidata"
        }
        assert "Q122922" in qids
    finally:
        session.close()


def test_overrides_page_source_urls_are_links(client) -> None:
    records = records_from_file(SAMPLE_SPARQL_FIXTURE)
    session = get_session()
    try:
        apply_import(session, records, "wikidata", make_backup=False)
        place = session.scalar(select(Place).where(Place.name == "Bouzov"))
        assert place is not None
        public_id = place.public_id
    finally:
        session.close()

    page = client.get(f"/places/{public_id}/overrides")
    assert page.status_code == 200
    assert 'href="https://www.wikidata.org/wiki/Q122922"' in page.text
    assert 'href="https://cs.wikipedia.org/wiki/Bouzov_(hrad)"' in page.text
    assert "Karty níže už patří" in page.text


def test_import_progress_fragment(client) -> None:
    from app.services.import_progress import write_progress

    response = client.get("/import/progress")
    assert response.status_code == 200
    page = client.get("/import")
    assert 'hx-get="/import/progress"' in page.text
    assert "import-live" in page.text
    home = client.get("/")
    assert 'hx-get="/import/progress"' in home.text

    write_progress(
        status="running",
        kind="preview",
        current=12,
        total=40,
        message="Náhled 12 / 40",
        force=True,
    )
    live = client.get("/import/progress")
    assert "12 / 40" in live.text
    assert "Náhled 12 / 40" in live.text
    assert "Jde o náhled" in live.text

    write_progress(
        status="applied",
        current=40,
        total=40,
        message="Import zapsán: 40 / 40",
        force=True,
    )
    just_done = client.get("/import/progress")
    assert "import-progress" in just_done.text
    assert "Import zapsán" in just_done.text

    write_progress(
        status="applied",
        current=4218,
        total=4218,
        message="Import zapsán: 4218 / 4218",
        updated_at=1.0,
        force=True,
    )
    stale = client.get("/import/progress")
    assert "import-progress" not in stale.text
    assert "4218" not in stale.text


def test_preview_result_filters_by_match_level(client) -> None:
    from app.services.matching import LEVEL_A, LEVEL_D, normalize_level_filter

    assert normalize_level_filter("d") == LEVEL_D
    assert normalize_level_filter("A") == LEVEL_A
    assert normalize_level_filter("MATCHED_PROBABLE") == "MATCHED_PROBABLE"
    assert normalize_level_filter("nope") == ""

    client.post("/import/preview", data={"fixture": DEFAULT_FIXTURE.name}, follow_redirects=True)
    page = client.get("/import/preview-result")
    assert page.status_code == 200
    assert "Úroveň shody" in page.text
    assert 'name="level"' in page.text
    assert "Nové místo" in page.text

    only_d = client.get("/import/preview-result", params={"level": "D"})
    assert only_d.status_code == 200
    assert "Nové místo" in only_d.text
    assert "záznamů" in only_d.text

    only_a = client.get("/import/preview-result", params={"level": "A"})
    assert only_a.status_code == 200
    assert "0 záznamů" in only_a.text
    assert "Přesná shoda" in only_a.text


def test_pc_ui_vendor_assets_are_local(client) -> None:
    home = client.get("/")
    assert home.status_code == 200
    assert "cdn.jsdelivr.net" not in home.text
    assert "unpkg.com" not in home.text
    assert "/static/vendor/pico/pico.min.css" in home.text
    assert "/static/vendor/htmx/htmx.min.js" in home.text
    assert client.get("/static/vendor/pico/pico.min.css").status_code == 200
    assert client.get("/static/vendor/htmx/htmx.min.js").status_code == 200

    nearby = client.get("/nearby")
    assert nearby.status_code == 200
    assert "unpkg.com" not in nearby.text
    assert "/static/vendor/leaflet/leaflet.js" in nearby.text
    assert "/static/vendor/leaflet/leaflet.css" in nearby.text
    assert client.get("/static/vendor/leaflet/leaflet.js").status_code == 200
    assert client.get("/static/vendor/leaflet/images/marker-icon.png").status_code == 200


def test_theme_toggle_in_base_layout(client) -> None:
    home = client.get("/")
    assert home.status_code == 200
    assert 'localStorage.getItem("pamatky-theme")' in home.text
    assert 'id="theme-preference"' in home.text
    assert "Systém" in home.text
    assert "Světlý" in home.text
    assert "Tmavý" in home.text
    assert 'data-theme' in home.text


