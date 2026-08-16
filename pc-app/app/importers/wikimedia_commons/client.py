"""MediaWiki API Wikimedia Commons — jen metadata, ne soubory."""

from __future__ import annotations

from typing import Any

import httpx

from app.importers.http_client import fetch_json
from app.importers.wikimedia_commons.parser import API
from app.logging_setup import get_logger

_log = get_logger()


class CommonsClient:
    def __init__(
        self,
        *,
        timeout: float = 40.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Any = None,
    ) -> None:
        self.timeout = timeout
        self._transport = transport
        self._sleep = sleep

    def fetch_imageinfo(self, filenames: list[str]) -> dict[str, Any]:
        titles = []
        for name in filenames:
            clean = name.replace(" ", "_")
            if not clean.lower().startswith("file:"):
                clean = f"File:{clean}"
            titles.append(clean)
        merged: dict[str, Any] = {"query": {"pages": {}}}
        kwargs: dict[str, Any] = {"timeout": self.timeout, "transport": self._transport}
        if self._sleep is not None:
            kwargs["sleep"] = self._sleep
        for offset in range(0, len(titles), 50):
            chunk = titles[offset : offset + 50]
            _log.info("commons imageinfo count=%s", len(chunk))
            payload = fetch_json(
                API,
                params={
                    "action": "query",
                    "format": "json",
                    "prop": "imageinfo",
                    "iiprop": "url|extmetadata|mime",
                    "iiurlwidth": "640",
                    "titles": "|".join(chunk),
                },
                **kwargs,
            )
            pages = ((payload.get("query") or {}).get("pages") or {}) if isinstance(payload, dict) else {}
            if isinstance(pages, dict):
                merged["query"]["pages"].update(pages)
        return merged
