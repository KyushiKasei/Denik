"""Deduplikace importu: úrovně A / B / C / D podle PLAN.md kapitoly 8."""

from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from math import ceil, cos, floor, radians

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ImportReview, Place, PlacePhoto, PlaceSource
from app.importers.base import CanonicalRecord
from app.importers.wikimedia_commons.parser import commons_filename
from app.services.geo import METERS_PER_DEG_LAT, MIN_COS_LAT, distance_m

LEVEL_A = "MATCHED_EXACT"
LEVEL_B = "MATCHED_PROBABLE"
LEVEL_C = "IMPORT_REVIEW"
LEVEL_D = "NEW_PLACE"
LEVEL_IGNORED = "IGNORED"
LEVEL_FAILED = "FAILED"

LEVEL_FILTER_ALIASES = {
    "A": LEVEL_A,
    "B": LEVEL_B,
    "C": LEVEL_C,
    "D": LEVEL_D,
}

ALL_MATCH_LEVELS = frozenset({LEVEL_A, LEVEL_B, LEVEL_C, LEVEL_D, LEVEL_IGNORED, LEVEL_FAILED})

LEVEL_FILTER_OPTIONS = (
    ("", "Všechny"),
    (LEVEL_A, "A · Přesná shoda"),
    (LEVEL_B, "B · Pravděpodobná shoda"),
    (LEVEL_C, "C · K rozhodnutí"),
    (LEVEL_D, "D · Nové místo"),
    (LEVEL_IGNORED, "Ignorováno"),
    (LEVEL_FAILED, "Chyba"),
)

PREVIEW_OUTCOME_LIMIT = 100


def normalize_level_filter(raw: str | None) -> str:
    value = (raw or "").strip().upper()
    if not value:
        return ""
    if value in LEVEL_FILTER_ALIASES:
        return LEVEL_FILTER_ALIASES[value]
    if value in ALL_MATCH_LEVELS:
        return value
    return ""


TYPE_FAMILY = frozenset({"CASTLE", "CHATEAU", "RUIN", "MANOR", "PALACE", "FORTRESS"})
_PREFIX_RE = re.compile(
    r"^(statni hrad|statni zamek|hrad|zamek|zricenina|tvrz|zamecek)\s+",
    re.IGNORECASE,
)
def strip_diacritics(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(char for char in normalized if not unicodedata.combining(char))


def normalize_label(value: str | None) -> str:
    """Obec / okres: lowercase, bez diakritiky, sjednocené mezery."""
    if not value:
        return ""
    text = strip_diacritics(value).lower()
    return re.sub(r"\s+", " ", text).strip()


def normalize_name(value: str | None) -> str:
    """Název pro matching: + odstranění prefixů hrad/zámek/…"""
    text = normalize_label(value)
    if not text:
        return ""
    for _ in range(3):
        stripped = _PREFIX_RE.sub("", text).strip()
        if stripped == text:
            break
        text = stripped
    return text


_LOCALITY_HINT_RE = re.compile(
    r"retrodil|dil uzemi|byv\.?\s*mestys|katastr|"
    r",\s*(ves|mesto|mestys)\b|"
    r"^\d{2,}",
    re.IGNORECASE,
)


def is_locality_alias(value: str | None, municipality: str | None = None) -> bool:
    """Katastr / část obce / RÚIAN popisek není alternativní název památky."""
    if not value or not str(value).strip():
        return False
    text = strip_diacritics(value).lower().strip()
    if _LOCALITY_HINT_RE.search(text):
        return True
    if "," in text and re.search(r"\d{3,}", text):
        return True
    if re.search(r"\b[ivx]+-", text):
        return True
    if municipality and normalize_label(value) == normalize_label(municipality):
        return True
    return False


def photo_filenames_from_record(record: CanonicalRecord) -> set[str]:
    """Soubory Wikimedia Commons na importovaném záznamu (P18 / Commons ID)."""
    names: set[str] = set()
    if record.source_type == "wikimedia_commons" and record.external_id:
        names.add(str(record.external_id).replace(" ", "_"))
    for source_type, external_id in record.all_external_ids():
        if source_type == "wikimedia_commons" and external_id:
            names.add(str(external_id).replace(" ", "_"))
    image = record.image if isinstance(record.image, dict) else None
    if image:
        filename = image.get("filename")
        if filename:
            names.add(str(filename).replace(" ", "_"))
        for key in ("original_url", "source_url", "thumbnail_url"):
            found = commons_filename(image.get(key))
            if found:
                names.add(found)
    names.discard("")
    return names


def photo_filenames_from_photos(photos: list) -> set[str]:
    names: set[str] = set()
    for photo in photos:
        for url in (getattr(photo, "original_url", None), getattr(photo, "source_url", None), getattr(photo, "thumbnail_url", None)):
            found = commons_filename(url)
            if found:
                names.add(found)
    return names


def photo_filenames_from_place(place: Place) -> set[str]:
    return photo_filenames_from_photos(list(place.photos))


def names_for_match(primary: str | None, alternatives: list[str], municipality: str | None = None) -> list[str]:
    names: list[str] = []
    if primary and str(primary).strip():
        names.append(str(primary).strip())
    for alt in alternatives:
        if not alt or not str(alt).strip():
            continue
        if is_locality_alias(alt, municipality):
            continue
        names.append(str(alt).strip())
    return names


def name_similarity(left: str, right: str) -> float:
    a = normalize_name(left)
    b = normalize_name(right)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    return SequenceMatcher(None, a, b).ratio()


def best_name_similarity(incoming: CanonicalRecord, place: Place) -> float:
    incoming_names = names_for_match(incoming.name, incoming.alternative_names, incoming.municipality)
    place_names = names_for_match(place.name, place.alt_names, place.municipality)
    best = 0.0
    for left in incoming_names:
        for right in place_names:
            best = max(best, name_similarity(left, right))
    return best


def names_identical(incoming: CanonicalRecord, place: Place) -> bool:
    incoming_norm = {
        normalize_name(n)
        for n in names_for_match(incoming.name, incoming.alternative_names, incoming.municipality)
    }
    place_norm = {normalize_name(n) for n in names_for_match(place.name, place.alt_names, place.municipality)}
    incoming_norm.discard("")
    place_norm.discard("")
    return bool(incoming_norm & place_norm)


def shared_specific_name(incoming: CanonicalRecord, place: Place) -> bool:
    """Společný normalizovaný název není holé ‚zámek/hrad/…‘ — OSM centroid vs. bod katalogu."""
    incoming_norm = {
        normalize_name(n)
        for n in names_for_match(incoming.name, incoming.alternative_names, incoming.municipality)
    }
    place_norm = {normalize_name(n) for n in names_for_match(place.name, place.alt_names, place.municipality)}
    shared = (incoming_norm & place_norm) - {""}
    return any(len(key) >= _MIN_SPECIFIC_NAME_LEN and key not in _GENERIC_NAME_KEYS for key in shared)


def types_compatible(left: set[str], right: set[str]) -> bool:
    """Prázdná strana, neprázdný průnik, nebo rodina hrad/zámek/zřícenina/tvrz/palác/pevnost.

    OTHER samo o sobě nestačí k automatickému sloučení s jiným typem.
    """
    if not left or not right:
        return True
    if left & right:
        return True
    if (left & TYPE_FAMILY) and (right & TYPE_FAMILY):
        return True
    return False


def same_or_missing_municipality(left: str | None, right: str | None) -> bool:
    a, b = normalize_label(left), normalize_label(right)
    if not a or not b:
        return True
    return a == b


def same_municipality(left: str | None, right: str | None) -> bool:
    a, b = normalize_label(left), normalize_label(right)
    return bool(a) and a == b


def same_district(left: str | None, right: str | None) -> bool:
    a, b = normalize_label(left), normalize_label(right)
    return bool(a) and a == b


@dataclass
class MatchCandidate:
    place: Place
    score: float
    reason: str
    distance_m: float | None = None
    name_similarity: float | None = None


@dataclass
class MatchDecision:
    level: str
    action: str
    reason: str
    place: Place | None = None
    candidates: list[MatchCandidate] = field(default_factory=list)


_CELL_DEG = 0.002
_B_RADIUS_M = 350.0
_C_RADIUS_M = 500.0
_B1_DISTANCE_M = 100.0
_B1_SIMILARITY = 0.90
_B2_DISTANCE_M = 300.0
_B3_DISTANCE_M = 80.0
_B4_DISTANCE_M = 300.0
_C1_DISTANCE_M = 400.0
_C1_SIMILARITY = 0.75
_C2_SIMILARITY = 0.82
_GENERIC_NAME_KEYS = frozenset(
    {"zamek", "hrad", "tvrz", "zricenina", "zamecek", "palac", "pevnost"}
)
_MIN_SPECIFIC_NAME_LEN = 4


def is_ignored(session: Session, record: CanonicalRecord) -> bool:
    if not record.external_id:
        return False
    existing = session.scalar(
        select(ImportReview.id).where(
            ImportReview.source_type == record.source_type,
            ImportReview.external_id == record.external_id,
            ImportReview.status == "ignored",
        )
    )
    return existing is not None


def _geo_cell(lat: float, lon: float) -> tuple[int, int]:
    return (int(floor(lat / _CELL_DEG)), int(floor(lon / _CELL_DEG)))


@dataclass
class _IndexEntry:
    place: Place
    name_keys: set[str]
    muni_key: str
    district_key: str
    cell: tuple[int, int] | None
    ext_keys: list[tuple[str, str]]
    photo_keys: list[str]
    active: bool


class MatchIndex:
    """Jednou načte katalog a páruje A/B/C bez SQL a bez SequenceMatcher na všech místech."""

    def __init__(self, session: Session) -> None:
        self.session = session
        self.ignored: set[tuple[str, str]] = set()
        self.entries: dict[int, _IndexEntry] = {}
        self.by_ext: dict[tuple[str, str], list[Place]] = defaultdict(list)
        self.by_photo: dict[str, list[Place]] = defaultdict(list)
        self.by_name: dict[str, set[int]] = defaultdict(set)
        self.by_muni: dict[str, set[int]] = defaultdict(set)
        self.by_district: dict[str, set[int]] = defaultdict(set)
        self.by_cell: dict[tuple[int, int], set[int]] = defaultdict(set)

    @classmethod
    def build(cls, session: Session) -> MatchIndex:
        index = cls(session)
        ignored_rows = session.execute(
            select(ImportReview.source_type, ImportReview.external_id).where(
                ImportReview.status == "ignored"
            )
        )
        index.ignored = {
            (str(source_type), str(external_id))
            for source_type, external_id in ignored_rows
            if source_type and external_id
        }
        places = list(session.scalars(select(Place).order_by(Place.id)).all())
        for place in places:
            index.register(place)
        return index

    def drop(self, place_id: int) -> None:
        entry = self.entries.pop(place_id, None)
        if entry is None:
            return
        for key in entry.ext_keys:
            remaining = [item for item in self.by_ext.get(key, []) if item.id != place_id]
            if remaining:
                self.by_ext[key] = remaining
            else:
                self.by_ext.pop(key, None)
        for key in entry.photo_keys:
            remaining = [item for item in self.by_photo.get(key, []) if item.id != place_id]
            if remaining:
                self.by_photo[key] = remaining
            else:
                self.by_photo.pop(key, None)
        if not entry.active:
            return
        for key in entry.name_keys:
            bucket = self.by_name.get(key)
            if bucket is not None:
                bucket.discard(place_id)
                if not bucket:
                    del self.by_name[key]
        if entry.muni_key:
            bucket = self.by_muni.get(entry.muni_key)
            if bucket is not None:
                bucket.discard(place_id)
                if not bucket:
                    del self.by_muni[entry.muni_key]
        if entry.district_key:
            bucket = self.by_district.get(entry.district_key)
            if bucket is not None:
                bucket.discard(place_id)
                if not bucket:
                    del self.by_district[entry.district_key]
        if entry.cell is not None:
            bucket = self.by_cell.get(entry.cell)
            if bucket is not None:
                bucket.discard(place_id)
                if not bucket:
                    del self.by_cell[entry.cell]

    def register(self, place: Place) -> None:
        if place.id is None:
            return
        self.drop(place.id)
        sources = list(
            self.session.scalars(select(PlaceSource).where(PlaceSource.place_id == place.id)).all()
        )
        photos = list(
            self.session.scalars(select(PlacePhoto).where(PlacePhoto.place_id == place.id)).all()
        )
        ext_keys: list[tuple[str, str]] = []
        for source in sources:
            if source.external_id:
                key = (source.source_type, source.external_id)
                self.by_ext[key].append(place)
                ext_keys.append(key)
        photo_keys = sorted(photo_filenames_from_photos(photos))
        active = place.archived_at is None
        name_keys = {
            normalize_name(name)
            for name in names_for_match(place.name, place.alt_names, place.municipality)
        }
        name_keys.discard("")
        muni_key = normalize_label(place.municipality)
        district_key = normalize_label(place.district)
        cell = None
        if place.latitude is not None and place.longitude is not None:
            cell = _geo_cell(place.latitude, place.longitude)
        entry = _IndexEntry(
            place=place,
            name_keys=name_keys,
            muni_key=muni_key,
            district_key=district_key,
            cell=cell,
            ext_keys=ext_keys,
            photo_keys=photo_keys,
            active=active,
        )
        self.entries[place.id] = entry
        if not active:
            return
        for key in photo_keys:
            self.by_photo[key].append(place)
        for key in name_keys:
            self.by_name[key].add(place.id)
        if muni_key:
            self.by_muni[muni_key].add(place.id)
        if district_key:
            self.by_district[district_key].add(place.id)
        if cell is not None:
            self.by_cell[cell].add(place.id)

    def _places_by_ids(self, ids: set[int]) -> list[Place]:
        out: list[Place] = []
        for place_id in ids:
            entry = self.entries.get(place_id)
            if entry is not None and entry.active:
                out.append(entry.place)
        return out

    def _nearby_ids(self, lat: float, lon: float, radius_m: float) -> set[int]:
        lat_m = METERS_PER_DEG_LAT
        lon_m = METERS_PER_DEG_LAT * max(MIN_COS_LAT, abs(cos(radians(lat))))
        lat_cells = int(ceil(radius_m / (lat_m * _CELL_DEG))) + 1
        lon_cells = int(ceil(radius_m / (lon_m * _CELL_DEG))) + 1
        origin = _geo_cell(lat, lon)
        ids: set[int] = set()
        for dy in range(-lat_cells, lat_cells + 1):
            for dx in range(-lon_cells, lon_cells + 1):
                cell = (origin[0] + dy, origin[1] + dx)
                bucket = self.by_cell.get(cell)
                if bucket:
                    ids.update(bucket)
        return ids

    def _name_ids(self, record: CanonicalRecord) -> set[int]:
        ids: set[int] = set()
        for name in names_for_match(record.name, record.alternative_names, record.municipality):
            key = normalize_name(name)
            if key:
                ids.update(self.by_name.get(key, ()))
        return ids

    def _b_candidates(self, record: CanonicalRecord) -> list[Place]:
        ids: set[int] = set()
        if record.latitude is not None and record.longitude is not None:
            ids.update(self._nearby_ids(record.latitude, record.longitude, _B_RADIUS_M))
        muni = normalize_label(record.municipality)
        if muni:
            ids.update(self._name_ids(record) & self.by_muni.get(muni, set()))
        return self._places_by_ids(ids)

    def _c_candidates(self, record: CanonicalRecord) -> list[Place]:
        ids = self._name_ids(record)
        muni = normalize_label(record.municipality)
        if muni:
            ids.update(self.by_muni.get(muni, ()))
        if record.latitude is not None and record.longitude is not None:
            ids.update(self._nearby_ids(record.latitude, record.longitude, _C_RADIUS_M))
        return self._places_by_ids(ids)

    def match(self, record: CanonicalRecord) -> MatchDecision:
        if not (record.name or "").strip():
            return MatchDecision(level=LEVEL_FAILED, action="fail", reason="Chybí název.")
        if record.external_id and (record.source_type, record.external_id) in self.ignored:
            return MatchDecision(
                level=LEVEL_IGNORED,
                action="ignore",
                reason=f"Ignorováno: {record.source_type}/{record.external_id}",
            )

        exact: dict[int, Place] = {}
        for source_type, external_id in record.all_external_ids():
            for place in self.by_ext.get((source_type, external_id), ()):
                exact[place.id] = place
        photo_hits: dict[int, Place] = {}
        for filename in photo_filenames_from_record(record):
            for place in self.by_photo.get(filename, ()):
                photo_hits[place.id] = place
                exact[place.id] = place
        if len(exact) == 1:
            place = next(iter(exact.values()))
            ids = ", ".join(f"{s}:{i}" for s, i in record.all_external_ids())
            if place.id in photo_hits and not ids:
                reason = f"A same commons photo ({next(iter(photo_filenames_from_record(record)))})"
            elif place.id in photo_hits:
                reason = f"A exact external id or same commons photo ({ids})"
            else:
                reason = f"A exact external id ({ids})"
            return MatchDecision(
                level=LEVEL_A,
                action="update",
                reason=reason,
                place=place,
                candidates=[_candidate(record, place, ["exact external id" if place.id not in photo_hits else "same commons photo"])],
            )
        if len(exact) > 1:
            candidates = [
                _candidate(
                    record,
                    place,
                    ["same commons photo"] if place.id in photo_hits else ["exact external id on different Place"],
                )
                for place in exact.values()
            ]
            return MatchDecision(
                level=LEVEL_C,
                action="review",
                reason="A: stejné ID nebo stejná fotka na více různých Place — neslučovat",
                candidates=sorted(candidates, key=lambda c: c.score, reverse=True),
            )

        b_hits: list[MatchCandidate] = []
        for place in self._b_candidates(record):
            reasons = _b_reasons(record, place)
            if reasons:
                b_hits.append(_candidate(record, place, reasons))

        if len(b_hits) == 1:
            hit = b_hits[0]
            return MatchDecision(
                level=LEVEL_B,
                action="update",
                reason=hit.reason,
                place=hit.place,
                candidates=b_hits,
            )
        if len(b_hits) > 1:
            return MatchDecision(
                level=LEVEL_C,
                action="review",
                reason="B: více Place vyhovuje pravděpodobné shodě — neslučovat",
                candidates=sorted(b_hits, key=lambda c: c.score, reverse=True),
            )

        c_hits: list[MatchCandidate] = []
        for place in self._c_candidates(record):
            reasons = _c_reasons(record, place)
            if reasons:
                c_hits.append(_candidate(record, place, reasons))
        if c_hits:
            c_hits.sort(key=lambda c: c.score, reverse=True)
            return MatchDecision(
                level=LEVEL_C,
                action="review",
                reason=c_hits[0].reason,
                candidates=c_hits,
            )

        if not record.allow_create:
            return MatchDecision(
                level=LEVEL_FAILED,
                action="fail",
                reason="Zdroj jen obohacuje existující místa, nové se nezakládá.",
            )
        return MatchDecision(level=LEVEL_D, action="create", reason="Žádný kandidát A/B/C")


def _place_types(place: Place) -> set[str]:
    return {item.code for item in place.types}


def _incoming_types(record: CanonicalRecord) -> set[str]:
    return {code for code in record.types if code}


def _b_reasons(record: CanonicalRecord, place: Place) -> list[str]:
    """Vrátí splněné sady úrovně B (prázdné = nesplňuje B)."""
    dist = distance_m(record.latitude, record.longitude, place.latitude, place.longitude)
    sim = best_name_similarity(record, place)
    identical = names_identical(record, place)
    muni_ok = same_or_missing_municipality(record.municipality, place.municipality)
    same_muni = same_municipality(record.municipality, place.municipality)
    same_dist = same_district(record.district, place.district)
    types_ok = types_compatible(_incoming_types(record), _place_types(place))
    reasons: list[str] = []

    if (
        dist is not None
        and dist <= _B1_DISTANCE_M
        and sim >= _B1_SIMILARITY
        and muni_ok
        and types_ok
    ):
        reasons.append(f"B1 distance={dist:.1f}m similarity={sim:.3f} municipality/types ok")
    if identical and same_muni and dist is not None and dist <= _B2_DISTANCE_M:
        reasons.append(f"B2 identical_name same_municipality distance={dist:.1f}m")
    if identical and same_dist and dist is not None and dist <= _B3_DISTANCE_M:
        reasons.append(f"B3 identical_name same_district distance={dist:.1f}m")
    if (
        identical
        and types_ok
        and muni_ok
        and dist is not None
        and dist <= _B4_DISTANCE_M
        and shared_specific_name(record, place)
    ):
        reasons.append(
            f"B4 identical_name types ok municipality missing-or-same distance={dist:.1f}m"
        )
    if (
        identical
        and types_ok
        and same_muni
        and shared_specific_name(record, place)
        and (dist is None or dist <= _B2_DISTANCE_M)
    ):
        dist_bit = "no_gps" if dist is None else f"distance={dist:.1f}m"
        reasons.append(f"B5 identical_name same_municipality types ok {dist_bit}")
    return reasons


def _c_reasons(record: CanonicalRecord, place: Place) -> list[str]:
    dist = distance_m(record.latitude, record.longitude, place.latitude, place.longitude)
    sim = best_name_similarity(record, place)
    reasons: list[str] = []
    if dist is not None and dist <= _C1_DISTANCE_M and sim >= _C1_SIMILARITY:
        reasons.append(f"C1 distance={dist:.1f}m similarity={sim:.3f}")
    if same_municipality(record.municipality, place.municipality) and sim >= _C2_SIMILARITY:
        reasons.append(f"C2 same_municipality similarity={sim:.3f}")
    return reasons


def _candidate(record: CanonicalRecord, place: Place, reasons: list[str]) -> MatchCandidate:
    dist = distance_m(record.latitude, record.longitude, place.latitude, place.longitude)
    sim = best_name_similarity(record, place)
    return MatchCandidate(
        place=place,
        score=sim,
        reason="; ".join(reasons),
        distance_m=dist,
        name_similarity=sim,
    )


def match_record(
    session: Session,
    record: CanonicalRecord,
    index: MatchIndex | None = None,
) -> MatchDecision:
    if index is None:
        index = MatchIndex.build(session)
    return index.match(record)
