"""SPARQL klient pro query.wikidata.org. Povinný User-Agent, timeout, retry."""

from __future__ import annotations

import time
from typing import Any

import httpx

from app.importers.http_client import CONNECT_TIMEOUT, RETRY_STATUSES, USER_AGENT
from app.importers.wikidata.query import (
    TYPE_CLASSES,
    QID_BATCH_SIZE,
    build_condition_query,
    build_items_query,
    build_query,
    build_style_query,
)
from app.logging_setup import get_logger

ENDPOINT = "https://query.wikidata.org/sparql"
READ_TIMEOUT = 55.0
MAX_RETRIES = 3

_log = get_logger()


class SparqlError(RuntimeError):
    """Stažení SPARQL selhalo i po opakováních."""


class WikidataClient:
    def __init__(
        self,
        *,
        endpoint: str = ENDPOINT,
        user_agent: str = USER_AGENT,
        timeout: float = READ_TIMEOUT,
        max_retries: int = MAX_RETRIES,
        transport: httpx.BaseTransport | None = None,
        sleep: Any = time.sleep,
    ) -> None:
        self.endpoint = endpoint
        self.user_agent = user_agent
        self.timeout = httpx.Timeout(
            connect=CONNECT_TIMEOUT,
            read=timeout,
            write=CONNECT_TIMEOUT,
            pool=CONNECT_TIMEOUT,
        )
        self.max_retries = max_retries
        self._transport = transport
        self._sleep = sleep

    def fetch_class(self, class_qid: str) -> dict[str, Any]:
        query = build_query(class_qid)
        return self._request(query, class_qid)

    def fetch_items(self, qids: list[str], on_batch=None) -> dict[str, Any]:
        """SPARQL pro konkrétní QID — P18 u míst, která typové třídy minuly."""
        if not qids:
            return {"head": {"vars": []}, "results": {"bindings": []}}
        bindings: list[Any] = []
        batches = [qids[index : index + QID_BATCH_SIZE] for index in range(0, len(qids), QID_BATCH_SIZE)]
        for index, batch in enumerate(batches, start=1):
            _log.info("wikidata SPARQL existing qids batch=%s/%s size=%s", index, len(batches), len(batch))
            if on_batch is not None:
                on_batch(index, len(batches), len(batch))
            payload = self._request(build_items_query(batch), f"items:{index}")
            rows = payload.get("results", {}).get("bindings") if isinstance(payload.get("results"), dict) else None
            if isinstance(rows, list):
                bindings.extend(rows)
        return {"head": {"vars": []}, "results": {"bindings": bindings}}

    def fetch_conditions(self, qids: list[str], on_batch=None) -> dict[str, Any]:
        if not qids:
            return {"head": {"vars": []}, "results": {"bindings": []}}
        bindings: list[Any] = []
        batches = [qids[index : index + QID_BATCH_SIZE] for index in range(0, len(qids), QID_BATCH_SIZE)]
        for index, batch in enumerate(batches, start=1):
            _log.info("wikidata SPARQL condition batch=%s/%s size=%s", index, len(batches), len(batch))
            if on_batch is not None:
                on_batch(index, len(batches), len(batch))
            payload = self._request(build_condition_query(batch), f"condition:{index}")
            rows = payload.get("results", {}).get("bindings") if isinstance(payload.get("results"), dict) else None
            if isinstance(rows, list):
                bindings.extend(rows)
        return {"head": {"vars": []}, "results": {"bindings": bindings}}

    def fetch_styles(self, qids: list[str], on_batch=None) -> dict[str, Any]:
        if not qids:
            return {"head": {"vars": []}, "results": {"bindings": []}}
        bindings: list[Any] = []
        batches = [qids[index : index + QID_BATCH_SIZE] for index in range(0, len(qids), QID_BATCH_SIZE)]
        for index, batch in enumerate(batches, start=1):
            _log.info("wikidata SPARQL style batch=%s/%s size=%s", index, len(batches), len(batch))
            if on_batch is not None:
                on_batch(index, len(batches), len(batch))
            payload = self._request(build_style_query(batch), f"style:{index}")
            rows = payload.get("results", {}).get("bindings") if isinstance(payload.get("results"), dict) else None
            if isinstance(rows, list):
                bindings.extend(rows)
        return {"head": {"vars": []}, "results": {"bindings": bindings}}

    def fetch_bundle(self, on_type=None) -> dict[str, dict[str, Any]]:
        bundle: dict[str, dict[str, Any]] = {}
        items = list(TYPE_CLASSES.items())
        for index, (type_code, class_qid) in enumerate(items, start=1):
            _log.info("wikidata SPARQL type=%s class=%s", type_code, class_qid)
            if on_type is not None:
                on_type(type_code, index, len(items))
            bundle[type_code] = self.fetch_class(class_qid)
        return bundle

    def _request(self, query: str, class_qid: str) -> dict[str, Any]:
        headers = {
            "User-Agent": self.user_agent,
            "Accept": "application/sparql-results+json",
        }
        last_error: Exception | None = None
        with httpx.Client(
            timeout=self.timeout,
            headers=headers,
            follow_redirects=True,
            transport=self._transport,
        ) as client:
            for attempt in range(1, self.max_retries + 1):
                try:
                    response = client.post(
                        self.endpoint,
                        data={"query": query, "format": "json"},
                    )
                    if response.status_code in RETRY_STATUSES:
                        last_error = SparqlError(
                            f"SPARQL {class_qid} HTTP {response.status_code} (pokus {attempt})"
                        )
                        _log.warning("%s", last_error)
                        self._backoff(attempt)
                        continue
                    response.raise_for_status()
                    payload = response.json()
                    if not isinstance(payload, dict) or "results" not in payload:
                        raise SparqlError(f"SPARQL {class_qid}: neočekávaný JSON")
                    return payload
                except SparqlError:
                    raise
                except (
                    httpx.TimeoutException,
                    httpx.NetworkError,
                    httpx.RemoteProtocolError,
                    httpx.HTTPStatusError,
                ) as exc:
                    last_error = exc
                    _log.warning(
                        "wikidata SPARQL class=%s attempt=%s error=%s",
                        class_qid,
                        attempt,
                        exc,
                    )
                    if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code not in RETRY_STATUSES:
                        break
                    self._backoff(attempt)
        raise SparqlError(f"SPARQL dotaz {class_qid} selhal: {last_error}") from last_error

    def _backoff(self, attempt: int) -> None:
        if attempt < self.max_retries:
            self._sleep(2 * attempt)
