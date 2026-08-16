"""Metadata Wikimedia Commons k souboru z P18. Nestahuje se binární foto."""

from __future__ import annotations

import html
import re
from typing import Any
from urllib.parse import unquote, quote

from app.importers.base import CanonicalRecord

SOURCE_TYPE = "wikimedia_commons"
API = "https://commons.wikimedia.org/w/api.php"
_TAG_RE = re.compile(r"<[^>]+>")


def commons_filename(url: str | None) -> str | None:
    if not url:
        return None
    text = unquote(url)
    for marker in ("Special:FilePath/", "/wiki/File:", "File:"):
        if marker in text:
            name = text.split(marker, 1)[1]
            name = name.split("?")[0].split("#")[0]
            name = name.replace(" ", "_")
            return name or None
    if text.lower().endswith((".jpg", ".jpeg", ".png", ".gif", ".tif", ".tiff", ".webp", ".svg")):
        return text.rsplit("/", 1)[-1].replace(" ", "_")
    return None


def _strip_html(value: str | None) -> str | None:
    if not value:
        return None
    text = _TAG_RE.sub("", value)
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or None


def _meta(ext: dict[str, Any], key: str) -> str | None:
    cell = ext.get(key)
    if not isinstance(cell, dict):
        return None
    return _strip_html(str(cell.get("value") or ""))


def metadata_from_imageinfo(info: dict[str, Any], filename: str) -> dict[str, str]:
    ext = info.get("extmetadata") if isinstance(info.get("extmetadata"), dict) else {}
    author = _meta(ext, "Artist") or _meta(ext, "Credit")
    license_name = _meta(ext, "LicenseShortName") or _meta(ext, "License")
    license_url = _meta(ext, "LicenseUrl")
    attribution = _meta(ext, "Attribution")
    if not attribution:
        parts = [part for part in [author, "Wikimedia Commons", license_name] if part]
        attribution = " / ".join(parts) if parts else None
    quoted = quote(filename.replace(" ", "_"), safe="._-()")
    file_page = f"https://commons.wikimedia.org/wiki/File:{quoted}"
    thumb = info.get("thumburl") or f"https://commons.wikimedia.org/wiki/Special:FilePath/{quoted}?width=640"
    original = info.get("descriptionurl") or file_page
    payload: dict[str, str] = {
        "source": SOURCE_TYPE,
        "filename": filename.replace(" ", "_"),
        "original_url": original,
        "thumbnail_url": thumb,
        "source_url": file_page,
    }
    if author:
        payload["author"] = author
    if license_name:
        payload["license"] = license_name
    if license_url:
        payload["license_url"] = license_url
    if attribution:
        payload["attribution"] = attribution
    return payload


def records_from_imageinfo(
    payload: dict[str, Any],
    attachments: list[dict[str, Any]],
    fetched_at: str,
) -> list[CanonicalRecord]:
    """attachments: [{filename, name, external_ids, ...}] propojené s API pages."""
    pages = ((payload.get("query") or {}).get("pages") or {}) if isinstance(payload, dict) else {}
    by_title: dict[str, dict[str, Any]] = {}
    if isinstance(pages, dict):
        for page in pages.values():
            title = str(page.get("title") or "")
            infos = page.get("imageinfo") or []
            info = infos[0] if infos else {}
            key = title.replace("File:", "").replace(" ", "_")
            by_title[key.casefold()] = info if isinstance(info, dict) else {}
    records: list[CanonicalRecord] = []
    for item in attachments:
        filename = str(item.get("filename") or "").replace(" ", "_")
        if not filename:
            continue
        info = by_title.get(filename.casefold(), {})
        image = metadata_from_imageinfo(info, filename)
        external_ids = dict(item.get("external_ids") or {})
        external_ids[SOURCE_TYPE] = filename
        records.append(
            CanonicalRecord(
                source_type=SOURCE_TYPE,
                external_id=filename,
                external_ids=external_ids,
                name=str(item.get("name") or filename),
                types=list(item.get("types") or []),
                latitude=item.get("latitude"),
                longitude=item.get("longitude"),
                municipality=item.get("municipality"),
                image=image,
                license=image.get("license"),
                source_url=image.get("source_url"),
                raw={"filename": filename, "imageinfo": info},
                fetched_at=fetched_at,
                allow_create=False,
            )
        )
    return records
