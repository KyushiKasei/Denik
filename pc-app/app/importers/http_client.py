"""Sdílený HTTP klient pro importery. Povinný User-Agent, timeout, retry."""

from __future__ import annotations

import json
import time
from typing import Any

import httpx

from app.logging_setup import get_logger

USER_AGENT = (
    "PamatkyDenik/0.5 (personal local heritage catalog; "
    "https://www.wikidata.org/wiki/Wikidata:Data_access)"
)
CONNECT_TIMEOUT = 10.0
RETRY_STATUSES = frozenset({429, 502, 503, 504})

_log = get_logger()


class DownloadError(RuntimeError):
    """Stažení selhalo i po opakováních."""


def fetch_bytes(
    url: str,
    *,
    method: str = "GET",
    params: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 60.0,
    max_retries: int = 3,
    transport: httpx.BaseTransport | None = None,
    sleep: Any = time.sleep,
    accept: str | None = None,
) -> bytes:
    merged = {"User-Agent": USER_AGENT}
    if accept:
        merged["Accept"] = accept
    if headers:
        merged.update(headers)
    last_error: Exception | None = None
    with httpx.Client(
        timeout=httpx.Timeout(connect=CONNECT_TIMEOUT, read=timeout, write=CONNECT_TIMEOUT, pool=CONNECT_TIMEOUT),
        headers=merged,
        follow_redirects=True,
        transport=transport,
    ) as client:
        for attempt in range(1, max_retries + 1):
            try:
                response = client.request(method, url, params=params, data=data)
                if response.status_code in RETRY_STATUSES:
                    last_error = DownloadError(f"{url} HTTP {response.status_code} (pokus {attempt})")
                    _log.warning("%s", last_error)
                    if attempt < max_retries:
                        sleep(2 * attempt)
                    continue
                response.raise_for_status()
                return response.content
            except DownloadError:
                raise
            except (httpx.TimeoutException, httpx.NetworkError, httpx.HTTPStatusError) as exc:
                last_error = exc
                _log.warning("download url=%s attempt=%s error=%s", url, attempt, exc)
                if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code not in RETRY_STATUSES:
                    break
                if attempt < max_retries:
                    sleep(2 * attempt)
    raise DownloadError(f"Stažení selhalo: {url}: {last_error}") from last_error


def fetch_json(
    url: str,
    *,
    method: str = "GET",
    params: dict[str, Any] | None = None,
    data: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 60.0,
    max_retries: int = 3,
    transport: httpx.BaseTransport | None = None,
    sleep: Any = time.sleep,
) -> Any:
    raw = fetch_bytes(
        url,
        method=method,
        params=params,
        data=data,
        headers=headers,
        timeout=timeout,
        max_retries=max_retries,
        transport=transport,
        sleep=sleep,
        accept="application/json",
    )
    return json.loads(raw.decode("utf-8"))


def decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1250"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("cp1250", errors="replace")
