"""Stažení CSV otevřených dat Památkového katalogu."""

from __future__ import annotations

from typing import Any

import httpx

from app.importers.http_client import USER_AGENT, fetch_bytes
from app.importers.pamatkovy_katalog.parser import parse_csv_bytes
from app.logging_setup import get_logger

OPENDATA_BASE = "https://pamatkovykatalog.cz/opendata"
DATASETS: dict[str, str] = {
    "KP": f"{OPENDATA_BASE}/npu_opendata_KP.csv",
    "NKP": f"{OPENDATA_BASE}/npu_opendata_NKP.csv",
    "SD": f"{OPENDATA_BASE}/npu_opendata_SD.csv",
}

_log = get_logger()


class KatalogClient:
    def __init__(
        self,
        *,
        timeout: float = 90.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Any = None,
    ) -> None:
        self.timeout = timeout
        self._transport = transport
        self._sleep = sleep

    def fetch_tables(self, on_dataset=None) -> dict[str, list[dict[str, str]]]:
        tables: dict[str, list[dict[str, str]]] = {}
        kwargs: dict[str, Any] = {"timeout": self.timeout, "transport": self._transport}
        if self._sleep is not None:
            kwargs["sleep"] = self._sleep
        items = list(DATASETS.items())
        for index, (code, url) in enumerate(items, start=1):
            if on_dataset is not None:
                on_dataset(code, index, len(items))
            _log.info("pamatkovy_katalog download %s %s", code, url)
            raw = fetch_bytes(
                url,
                headers={"User-Agent": USER_AGENT, "Accept": "text/csv,text/plain,*/*"},
                **kwargs,
            )
            tables[code] = parse_csv_bytes(raw)
        return tables
