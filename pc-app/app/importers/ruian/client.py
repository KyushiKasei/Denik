"""Stažení číselníků RÚIAN (obce, okresy, VÚSC). Bez adresních míst."""

from __future__ import annotations

import io
import zipfile
from typing import Any

import httpx

from app.importers.http_client import fetch_bytes
from app.importers.ruian.parser import parse_codebook_bytes
from app.logging_setup import get_logger

CIS_BASE = "https://services.cuzk.gov.cz/sestavy/cis"
FILES = {
    "obce": f"{CIS_BASE}/UI_OBEC.zip",
    "okresy": f"{CIS_BASE}/UI_OKRES.zip",
    "kraje": f"{CIS_BASE}/UI_VUSC.zip",
}

_log = get_logger()


def _unzip_first_csv(data: bytes) -> bytes:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
        if not names:
            raise ValueError("ZIP RÚIAN neobsahuje CSV")
        return archive.read(names[0])


class RuianClient:
    def __init__(
        self,
        *,
        timeout: float = 60.0,
        transport: httpx.BaseTransport | None = None,
        sleep: Any = None,
    ) -> None:
        self.timeout = timeout
        self._transport = transport
        self._sleep = sleep

    def fetch_tables(self) -> dict[str, list[dict[str, str]]]:
        tables: dict[str, list[dict[str, str]]] = {}
        kwargs: dict[str, Any] = {"timeout": self.timeout, "transport": self._transport}
        if self._sleep is not None:
            kwargs["sleep"] = self._sleep
        for key, url in FILES.items():
            _log.info("ruian download %s", url)
            zipped = fetch_bytes(url, **kwargs)
            tables[key] = parse_codebook_bytes(_unzip_first_csv(zipped))
        return tables
