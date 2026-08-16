"""Wikipedia — jen URL a kontrola úplnosti, ne kopírování článků."""

from __future__ import annotations

from typing import Any
from urllib.parse import quote, unquote

from app.importers.base import CanonicalRecord

SOURCE_TYPE = "wikipedia"
LICENSE = "CC BY-SA 4.0 (URL only; article text is not stored)"

_TYPE_BY_CATEGORY = {
    "Kategorie:Hrady_v_Česku": "CASTLE",
    "Kategorie:Zámky_v_Česku": "CHATEAU",
    "Kategorie:Zříceniny_hradů_v_Česku": "RUIN",
    "Kategorie:Tvrze_v_Česku": "MANOR",
    "Kategorie:Rozhledny_v_Česku": "LOOKOUT_TOWER",
    "Kategorie:Zoologické_zahrady_v_Česku": "ZOO",
    "Kategorie:Jeskyně_v_Česku": "CAVE",
}
CATEGORIES = tuple(_TYPE_BY_CATEGORY)


def _norm_category(value: str) -> str:
    return value.replace(" ", "_").casefold()


def title_to_url(title: str, lang: str = "cs") -> str:
    page = quote(title.replace(" ", "_"), safe="()_,-")
    return f"https://{lang}.wikipedia.org/wiki/{page}"


def type_from_category(category: str | None) -> list[str]:
    if not category:
        return []
    key = _norm_category(category)
    for title, code in _TYPE_BY_CATEGORY.items():
        if _norm_category(title) == key:
            return [code]
    return []


def record_from_page(
    *,
    title: str,
    qid: str | None,
    category: str | None,
    fetched_at: str,
    lang: str = "cs",
) -> CanonicalRecord | None:
    title = unquote(title.replace("_", " ")).strip()
    if not title:
        return None
    wiki_id = f"{lang}:{title.replace(' ', '_')}"
    url = title_to_url(title, lang)
    external_ids: dict[str, str] = {SOURCE_TYPE: wiki_id}
    if qid:
        external_ids["wikidata"] = qid
    return CanonicalRecord(
        source_type=SOURCE_TYPE,
        external_id=wiki_id,
        external_ids=external_ids,
        name=title.split("(")[0].strip() or title,
        types=type_from_category(category),
        wikipedia_url=url,
        source_url=url,
        license=LICENSE,
        raw={"title": title, "category": category, "qid": qid, "extract": None},
        fetched_at=fetched_at,
    )


def records_from_category_payload(payload: dict[str, Any], fetched_at: str) -> list[CanonicalRecord]:
    """Fixture/API tvar: {category: str, members: [{title, wikibase_item}]} nebo query.categorymembers."""
    records: list[CanonicalRecord] = []
    if "members" in payload:
        category = str(payload.get("category") or "")
        for item in payload.get("members") or []:
            if not isinstance(item, dict):
                continue
            record = record_from_page(
                title=str(item.get("title") or ""),
                qid=item.get("wikibase_item") or item.get("qid"),
                category=category,
                fetched_at=fetched_at,
            )
            if record is not None:
                records.append(record)
        return records
    members = ((payload.get("query") or {}).get("categorymembers") or []) if isinstance(payload, dict) else []
    category = str(payload.get("category") or "")
    for item in members:
        if not isinstance(item, dict):
            continue
        qid = None
        props = item.get("pageprops") or {}
        if isinstance(props, dict):
            qid = props.get("wikibase_item")
        record = record_from_page(
            title=str(item.get("title") or ""),
            qid=qid,
            category=category,
            fetched_at=fetched_at,
        )
        if record is not None:
            records.append(record)
    return records


def merge_wikipedia_records(records: list[CanonicalRecord]) -> list[CanonicalRecord]:
    by_id: dict[str, CanonicalRecord] = {}
    order: list[str] = []
    for record in records:
        key = record.external_id or record.name
        existing = by_id.get(key)
        if existing is None:
            by_id[key] = record
            order.append(key)
            continue
        types = list(dict.fromkeys([*existing.types, *record.types]))
        existing.types = types
        ids = dict(existing.external_ids)
        ids.update(record.external_ids)
        existing.external_ids = ids
    return [by_id[key] for key in order]
