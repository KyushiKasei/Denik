"""SPARQL: objekty s operátorem NPÚ. Žádný scraping npu.cz."""

from __future__ import annotations

from typing import Any

import httpx

from app.importers.http_client import fetch_json
from app.importers.npu.parser import NPU_QID
from app.logging_setup import get_logger

ENDPOINT = "https://query.wikidata.org/sparql"
_log = get_logger()


def build_managed_query() -> str:
    return f"""
SELECT DISTINCT ?item ?itemLabel ?web ?uskp WHERE {{
  ?item wdt:P17 wd:Q213 .
  {{
    ?item wdt:P137 wd:{NPU_QID} .
  }} UNION {{
    ?item wdt:P137 ?operator .
    ?operator (wdt:P361|wdt:P749)+ wd:{NPU_QID} .
  }} UNION {{
    ?item wdt:P127 wd:{NPU_QID} .
  }} UNION {{
    ?item wdt:P127 ?owner .
    ?owner (wdt:P361|wdt:P749)+ wd:{NPU_QID} .
  }}
  OPTIONAL {{ ?item wdt:P856 ?web . }}
  OPTIONAL {{ ?item wdt:P4075 ?uskp . }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "cs,en" . }}
}}
""".strip()


class NpuClient:
    def __init__(
        self,
        *,
        timeout: float = 55.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Any = None,
    ) -> None:
        self.timeout = timeout
        self._transport = transport
        self._sleep = sleep

    def fetch_sparql(self) -> dict[str, Any]:
        kwargs: dict[str, Any] = {"timeout": self.timeout, "transport": self._transport, "method": "POST"}
        if self._sleep is not None:
            kwargs["sleep"] = self._sleep
        _log.info("npu SPARQL operator=%s", NPU_QID)
        payload = fetch_json(
            ENDPOINT,
            data={"query": build_managed_query(), "format": "json"},
            **kwargs,
        )
        if not isinstance(payload, dict) or "results" not in payload:
            raise ValueError("Neočekávaná SPARQL odpověď NPÚ")
        return payload
