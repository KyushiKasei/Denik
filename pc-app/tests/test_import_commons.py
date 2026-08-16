from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import Place, PlacePhoto, PlaceSource
from app.importers.wikidata.importer import SAMPLE_SPARQL_FIXTURE, records_from_file as wikidata_records
from app.importers.wikimedia_commons.importer import records_from_sample
from app.importers.wikimedia_commons.parser import commons_filename
from app.services.apply_import import apply_import
from app.services.matching import LEVEL_A, match_record


def test_commons_filename_from_p18_url() -> None:
    assert commons_filename("http://commons.wikimedia.org/wiki/Special:FilePath/Hrad%20Bouzov.jpg") == "Hrad_Bouzov.jpg"


def test_commons_metadata_updates_photo_no_duplicate_place(session: Session) -> None:
    wiki = wikidata_records(SAMPLE_SPARQL_FIXTURE, fetched_at="t")
    apply_import(session, wiki, "wikidata", make_backup=True)
    bouzov = session.scalar(select(Place).where(Place.name == "Bouzov"))
    assert bouzov is not None
    public_id = bouzov.public_id
    photo = session.scalar(select(PlacePhoto).where(PlacePhoto.place_id == bouzov.id))
    assert photo is not None
    assert photo.author is None
    assert photo.license is None

    records = records_from_sample(fetched_at="t")
    assert records[0].image is not None
    assert records[0].image["author"] == "Jan Novák"
    assert records[0].image["license"] == "CC BY-SA 4.0"
    assert records[0].image["attribution"]
    decision = match_record(session, records[0])
    assert decision.level == LEVEL_A
    result = apply_import(session, records, "wikimedia_commons", make_backup=True)
    assert result.records_created == 0
    session.refresh(bouzov)
    session.refresh(photo)
    assert bouzov.public_id == public_id
    assert photo.author == "Jan Novák"
    assert photo.license == "CC BY-SA 4.0"
    assert photo.license_url and "creativecommons.org" in photo.license_url
    assert photo.attribution
    source = session.scalar(
        select(PlaceSource).where(
            PlaceSource.source_type == "wikimedia_commons",
            PlaceSource.external_id == "Hrad_Bouzov.jpg",
        )
    )
    assert source is not None
    assert source.place_id == bouzov.id
    assert source.license == "CC BY-SA 4.0"
    assert session.scalar(select(func.count()).select_from(Place)) == 6
    assert session.scalar(select(func.count()).select_from(PlacePhoto).where(PlacePhoto.place_id == bouzov.id)) == 1
