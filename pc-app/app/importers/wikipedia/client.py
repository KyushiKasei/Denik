"""MediaWiki API české Wikipedie — názvy stránek a QID, ne text článků."""

from __future__ import annotations

from typing import Any

import httpx

from app.importers.http_client import fetch_json
from app.importers.wikipedia.parser import CATEGORIES
from app.logging_setup import get_logger

API = "https://cs.wikipedia.org/w/api.php"
MAX_CATEGORY_CONTINUES = 40
_log = get_logger()


class WikipediaClient:
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

    def _kwargs(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"timeout": self.timeout, "transport": self._transport}
        if self._sleep is not None:
            kwargs["sleep"] = self._sleep
        return kwargs

    def fetch_category(self, category: str) -> dict[str, Any]:
        members: list[dict[str, Any]] = []
        cont: str | None = None
        for _ in range(MAX_CATEGORY_CONTINUES):
            params = {
                "action": "query",
                "format": "json",
                "list": "categorymembers",
                "cmtitle": category,
                "cmnamespace": "0",
                "cmlimit": "500",
                "cmprop": "title",
            }
            if cont:
                params["cmcontinue"] = cont
            payload = fetch_json(API, params=params, **self._kwargs())
            batch = ((payload.get("query") or {}).get("categorymembers") or []) if isinstance(payload, dict) else []
            members.extend([item for item in batch if isinstance(item, dict)])
            cont = ((payload.get("continue") or {}).get("cmcontinue")) if isinstance(payload, dict) else None
            if not cont:
                break
        else:
            _log.warning("wikipedia category=%s continue cap=%s", category, MAX_CATEGORY_CONTINUES)
        titles = [str(item.get("title")) for item in members if item.get("title")]
        by_title = {title: {"title": title} for title in titles}
        for offset in range(0, len(titles), 50):
            chunk = titles[offset : offset + 50]
            props = fetch_json(
                API,
                params={
                    "action": "query",
                    "format": "json",
                    "prop": "pageprops",
                    "ppprop": "wikibase_item",
                    "titles": "|".join(chunk),
                },
                **self._kwargs(),
            )
            pages = ((props.get("query") or {}).get("pages") or {}) if isinstance(props, dict) else {}
            if isinstance(pages, dict):
                for page in pages.values():
                    title = str(page.get("title") or "")
                    pp = page.get("pageprops") or {}
                    qid = pp.get("wikibase_item") if isinstance(pp, dict) else None
                    if title:
                        by_title[title] = {"title": title, "pageprops": {"wikibase_item": qid} if qid else {}}
        _log.info("wikipedia category=%s members=%s", category, len(by_title))
        return {"category": category, "query": {"categorymembers": list(by_title.values())}}

    def fetch_bundle(self) -> dict[str, dict[str, Any]]:
        return {category: self.fetch_category(category) for category in CATEGORIES}
