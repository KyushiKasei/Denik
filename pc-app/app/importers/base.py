"""Kanonický importní záznam. Importer nikdy nesahá do places přímo."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class CanonicalRecord:
    source_type: str
    name: str
    external_id: str | None = None
    external_ids: dict[str, str] = field(default_factory=dict)
    alternative_names: list[str] = field(default_factory=list)
    types: list[str] = field(default_factory=list)
    condition: str | None = None
    visitability: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    address: str | None = None
    municipality: str | None = None
    district: str | None = None
    region: str | None = None
    short_description: str | None = None
    official_website: str | None = None
    wikipedia_url: str | None = None
    heritage_status: str | None = None
    source_url: str | None = None
    license: str | None = None
    image: dict[str, Any] | None = None
    raw: dict[str, Any] = field(default_factory=dict)
    fetched_at: str = ""
    municipality_code: str | None = None
    district_code: str | None = None
    region_code: str | None = None
    opening_hours_url: str | None = None
    ticket_url: str | None = None
    unesco: int | None = None
    allow_create: bool = True

    def all_external_ids(self) -> list[tuple[str, str]]:
        """Jedinečné páry (source_type, external_id) včetně primary i mapy."""
        seen: set[tuple[str, str]] = set()
        out: list[tuple[str, str]] = []
        pairs: list[tuple[str, str]] = []
        if self.external_id:
            pairs.append((self.source_type, self.external_id))
        for source_type, external_id in self.external_ids.items():
            if external_id:
                pairs.append((source_type, str(external_id)))
        for pair in pairs:
            if pair not in seen:
                seen.add(pair)
                out.append(pair)
        return out

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CanonicalRecord:
        known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        payload = {key: value for key, value in data.items() if key in known}
        alts = payload.get("alternative_names") or []
        payload["alternative_names"] = [str(item) for item in alts]
        types = payload.get("types") or []
        payload["types"] = [str(item) for item in types]
        ids = payload.get("external_ids") or {}
        payload["external_ids"] = {str(k): str(v) for k, v in ids.items() if v}
        if payload.get("latitude") is not None:
            payload["latitude"] = float(payload["latitude"])
        if payload.get("longitude") is not None:
            payload["longitude"] = float(payload["longitude"])
        raw = payload.get("raw")
        payload["raw"] = raw if isinstance(raw, dict) else {}
        image = payload.get("image")
        payload["image"] = image if isinstance(image, dict) else None
        if payload.get("unesco") is not None:
            payload["unesco"] = 1 if payload["unesco"] in (1, True, "1", "true") else 0
        payload["allow_create"] = bool(payload.get("allow_create", True))
        return cls(**payload)
