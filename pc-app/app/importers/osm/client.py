"""Overpass API — volitelný doplněk (hrady, rozhledny, zoo, jeskyně) v ČR."""

from __future__ import annotations

import json
from typing import Any

import httpx

from app.importers.http_client import fetch_bytes
from app.logging_setup import get_logger

ENDPOINT = "https://overpass-api.de/api/interpreter"
_log = get_logger()

QUERY = """
[out:json][timeout:90];
area["ISO3166-1"="CZ"][admin_level=2];
(
  nwr["historic"="castle"](area);
  nwr["man_made"="tower"]["tower:type"="observation"](area);
  nwr["tourism"="zoo"](area);
  nwr["natural"="cave_entrance"](area);
);
out center tags;
""".strip()


class OsmClient:
    def __init__(
        self,
        *,
        timeout: float = 100.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Any = None,
    ) -> None:
        self.timeout = timeout
        self._transport = transport
        self._sleep = sleep

    def fetch_overpass(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {
            "timeout": self.timeout,
            "transport": self._transport,
            "method": "POST",
        }
        if self._sleep is not None:
            kwargs["sleep"] = self._sleep
        _log.info("osm Overpass castle/lookout/zoo/cave CZ")
        raw = fetch_bytes(
            ENDPOINT,
            data={"data": QUERY},
            accept="application/json",
            **kwargs,
        )
        payload = json.loads(raw.decode("utf-8"))
        if not isinstance(payload, dict) or "elements" not in payload:
            raise ValueError("Neočekávaná Overpass odpověď")
        return payload
