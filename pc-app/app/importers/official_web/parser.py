"""Odhad přístupnosti z homepage oficiálního webu. HTML se neukládá."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from html import unescape
from urllib.parse import urljoin, urlparse

from app.importers.base import CanonicalRecord
from app.services.source_urls import is_http_url

SOURCE_TYPE = "official_web"
LICENSE = "URL only; official website HTML is not stored"

_SKIP_HOST_SUFFIXES = (
    "wikipedia.org",
    "wikidata.org",
    "wikimedia.org",
    "facebook.com",
    "instagram.com",
    "youtube.com",
    "youtu.be",
    "twitter.com",
    "x.com",
    "mapy.cz",
    "google.com",
    "goo.gl",
    "hrady.cz",
    "kudyznudy.cz",
)

_POSITIVE = (
    "otevírací doba",
    "oteviraci doba",
    "návštěvní doba",
    "navstevni doba",
    "prohlídk",
    "prohlidk",
    "vstupenk",
    "koupit vstupenku",
    "opening hours",
    "buy ticket",
    "pro návštěvníky",
    "pro navstevniky",
    "prohlídkové trasy",
    "prohlidkove trasy",
    "informace pro návštěvníky",
    "informace pro navstevniky",
)

_HOURS_HREF = (
    "otevirac",
    "otevírac",
    "opening-hours",
    "opening_hours",
    "navstevni-doba",
    "navstevni_doba",
    "navstevni/doba",
    "visit/opening",
)

_TICKET_HREF = (
    "vstupne",
    "vstupenk",
    "tickets",
    "buy-ticket",
    "buy_ticket",
    "vstup/cena",
)

_ATTRACTION_TYPES = {
    "touristattraction",
    "castle",
    "museum",
    "landmarksorhistoricalbuildings",
    "civicstructure",
    "localbusiness",
    "touristinformationcenter",
}

_HREF_RE = re.compile(r"""(?is)<a[^>]+href=["']([^"']+)["']""")
_LD_SCRIPT_RE = re.compile(
    r"""(?is)<script[^>]*type=["']application/ld\+json["'][^>]*>(.*?)</script>"""
)
_SCRIPT_RE = re.compile(r"(?is)<script[^>]*>.*?</script>")
_STYLE_RE = re.compile(r"(?is)<style[^>]*>.*?</style>")
_TAG_RE = re.compile(r"(?is)<[^>]+>")
_SPACE_RE = re.compile(r"\s+")
_PUBLIC_ID_SPLIT_RE = re.compile(r"[\s,;]+")


@dataclass(frozen=True)
class WebsiteHint:
    visitability: str | None
    opening_hours_url: str | None
    ticket_url: str | None = None


def website_host(url: str | None) -> str | None:
    if not is_http_url(url):
        return None
    host = urlparse(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host or None


def skip_website(url: str | None) -> bool:
    host = website_host(url)
    if not host:
        return True
    return any(host == suffix or host.endswith("." + suffix) for suffix in _SKIP_HOST_SUFFIXES)


def parse_public_ids(raw: str | None) -> list[str]:
    if not raw or not str(raw).strip():
        return []
    seen: set[str] = set()
    out: list[str] = []
    for token in _PUBLIC_ID_SPLIT_RE.split(str(raw).strip()):
        value = token.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out


def html_to_text(html: str) -> str:
    cleaned = _SCRIPT_RE.sub(" ", html)
    cleaned = _STYLE_RE.sub(" ", cleaned)
    cleaned = _TAG_RE.sub(" ", cleaned)
    cleaned = unescape(cleaned)
    return _SPACE_RE.sub(" ", cleaned).strip()


def _absolute_http(raw: str, base_url: str) -> str | None:
    absolute = urljoin(base_url, raw)
    if is_http_url(absolute) and not skip_website(absolute):
        return absolute
    return None


def _href_url(html: str, base_url: str, tokens: tuple[str, ...]) -> str | None:
    for href in _HREF_RE.findall(html):
        raw = unescape(href).strip()
        if not raw or raw.startswith("#") or raw.lower().startswith("javascript:"):
            continue
        lowered = raw.casefold()
        if any(token in lowered for token in tokens):
            found = _absolute_http(raw, base_url)
            if found:
                return found
    return None


def _type_names(value: object) -> set[str]:
    items = value if isinstance(value, list) else [value]
    names: set[str] = set()
    for item in items:
        if not item:
            continue
        text = str(item).rsplit("/", 1)[-1].rsplit(":", 1)[-1]
        if text:
            names.add(text.casefold())
    return names


def _as_http_url(value: object, base_url: str) -> str | None:
    if not isinstance(value, str):
        return None
    raw = unescape(value).strip()
    if not raw:
        return None
    if is_http_url(raw):
        return raw if not skip_website(raw) else None
    if raw.startswith("/") or raw.startswith("./"):
        return _absolute_http(raw, base_url)
    return None


def _walk_jsonld(node: object, acc: dict[str, object], *, base_url: str) -> None:
    if isinstance(node, list):
        for item in node:
            _walk_jsonld(item, acc, base_url=base_url)
        return
    if not isinstance(node, dict):
        return
    types = _type_names(node.get("@type"))
    if types & _ATTRACTION_TYPES:
        acc["attraction"] = True
    hours = node.get("openingHours")
    spec = node.get("openingHoursSpecification")
    if hours or spec:
        acc["has_hours"] = True
        for candidate in (hours, spec if isinstance(spec, str) else None):
            url = _as_http_url(candidate, base_url)
            if url and not acc.get("hours_url"):
                acc["hours_url"] = url
        if isinstance(spec, dict):
            url = _as_http_url(spec.get("url") or spec.get("@id"), base_url)
            if url and not acc.get("hours_url"):
                acc["hours_url"] = url
        if isinstance(spec, list):
            for item in spec:
                if isinstance(item, dict):
                    url = _as_http_url(item.get("url") or item.get("@id"), base_url)
                    if url and not acc.get("hours_url"):
                        acc["hours_url"] = url
    if "offer" in types or node.get("price") is not None or node.get("priceCurrency"):
        url = _as_http_url(node.get("url") or node.get("@id"), base_url)
        if url and not acc.get("ticket_url"):
            acc["ticket_url"] = url
    offers = node.get("offers")
    if offers is not None:
        _walk_jsonld(offers, acc, base_url=base_url)
        if not acc.get("ticket_url"):
            url = _as_http_url(offers if isinstance(offers, str) else None, base_url)
            if url:
                acc["ticket_url"] = url
    for key, value in node.items():
        if key in {"@context", "openingHours", "openingHoursSpecification", "offers"}:
            continue
        if isinstance(value, (dict, list)):
            _walk_jsonld(value, acc, base_url=base_url)


def jsonld_hints(html: str, *, base_url: str) -> dict[str, object]:
    acc: dict[str, object] = {}
    for block in _LD_SCRIPT_RE.findall(html or ""):
        text = unescape(block).strip()
        if not text:
            continue
        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            continue
        _walk_jsonld(payload, acc, base_url=base_url)
    return acc


def classify_html(html: str, *, base_url: str) -> WebsiteHint:
    if not html or not html.strip():
        return WebsiteHint(None, None, None)
    ld = jsonld_hints(html, base_url=base_url)
    text = html_to_text(html).casefold()
    keywords = any(token in text for token in _POSITIVE)
    has_hours = bool(ld.get("has_hours"))
    attraction = bool(ld.get("attraction"))
    visitability = "REGULAR" if keywords or has_hours or attraction else None
    hours_href = _href_url(html, base_url, _HOURS_HREF)
    ticket_href = _href_url(html, base_url, _TICKET_HREF)
    hours_url = ld.get("hours_url") if isinstance(ld.get("hours_url"), str) else None
    ticket_url = ld.get("ticket_url") if isinstance(ld.get("ticket_url"), str) else None
    hours_url = hours_url or hours_href
    if not hours_url and (keywords or has_hours):
        hours_url = base_url
    ticket_url = ticket_url or ticket_href
    if visitability is None and (hours_url or ticket_url):
        visitability = "REGULAR"
    return WebsiteHint(visitability, hours_url, ticket_url)


def record_from_place(
    *,
    name: str,
    website: str,
    host: str,
    hint: WebsiteHint,
    external_ids: dict[str, str],
    fetched_at: str,
) -> CanonicalRecord | None:
    if hint.visitability is None and not hint.opening_hours_url and not hint.ticket_url:
        return None
    ids = dict(external_ids)
    ids[SOURCE_TYPE] = host
    return CanonicalRecord(
        source_type=SOURCE_TYPE,
        external_id=host,
        external_ids=ids,
        name=name,
        visitability=hint.visitability,
        official_website=website,
        opening_hours_url=hint.opening_hours_url,
        ticket_url=hint.ticket_url,
        source_url=website,
        license=LICENSE,
        raw={"note": "homepage classified; HTML not stored", "host": host},
        fetched_at=fetched_at,
        allow_create=False,
    )
