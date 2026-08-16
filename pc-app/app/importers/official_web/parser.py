"""Odhad přístupnosti z homepage oficiálního webu. HTML se neukládá."""

from __future__ import annotations

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

_HREF_RE = re.compile(r"""(?is)<a[^>]+href=["']([^"']+)["']""")
_SCRIPT_RE = re.compile(r"(?is)<script[^>]*>.*?</script>")
_STYLE_RE = re.compile(r"(?is)<style[^>]*>.*?</style>")
_TAG_RE = re.compile(r"(?is)<[^>]+>")
_SPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class WebsiteHint:
    visitability: str | None
    opening_hours_url: str | None


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


def html_to_text(html: str) -> str:
    cleaned = _SCRIPT_RE.sub(" ", html)
    cleaned = _STYLE_RE.sub(" ", cleaned)
    cleaned = _TAG_RE.sub(" ", cleaned)
    cleaned = unescape(cleaned)
    return _SPACE_RE.sub(" ", cleaned).strip()


def _hours_url(html: str, base_url: str) -> str | None:
    for href in _HREF_RE.findall(html):
        raw = unescape(href).strip()
        if not raw or raw.startswith("#") or raw.lower().startswith("javascript:"):
            continue
        lowered = raw.casefold()
        if any(token in lowered for token in _HOURS_HREF):
            absolute = urljoin(base_url, raw)
            if is_http_url(absolute):
                return absolute
    return None


def classify_html(html: str, *, base_url: str) -> WebsiteHint:
    if not html or not html.strip():
        return WebsiteHint(None, None)
    text = html_to_text(html).casefold()
    if not any(token in text for token in _POSITIVE):
        return WebsiteHint(None, None)
    hours = _hours_url(html, base_url)
    return WebsiteHint("REGULAR", hours or base_url)


def record_from_place(
    *,
    name: str,
    website: str,
    host: str,
    hint: WebsiteHint,
    external_ids: dict[str, str],
    fetched_at: str,
) -> CanonicalRecord | None:
    if hint.visitability is None:
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
        source_url=website,
        license=LICENSE,
        raw={"note": "homepage classified; HTML not stored", "host": host},
        fetched_at=fetched_at,
        allow_create=False,
    )
