from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping
from typing import Any

import httpx

from app.core.errors import RETRYABLE_KINDS, failure_kind
from app.core.retry_after import parse_headers

from .base import Adapter, ChatRequest, ChatResult, ProviderError, RerankRequest, RerankResult

__all__ = [
    "DOCUMENTS_MAX",
    "REQUEST_TIMEOUT",
    "RETRY_AFTER_CAP_SECONDS",
    "VOYAGE_API",
    "VOYAGE_SERVICE",
    "VoyageAdapter",
    "rerank_body",
    "rerank_result",
]

VOYAGE_API = "https://api.voyageai.com/v1"
VOYAGE_SERVICE = "voyage"
RERANK_PATH = "/rerank"
REQUEST_TIMEOUT = httpx.Timeout(15.0, connect=5.0)
RETRY_AFTER_CAP_SECONDS = 2.0
DOCUMENTS_MAX = 1000
RATE_LIMITED = 429

Sleep = Callable[[float], Awaitable[None]]


class VoyageAdapter(Adapter):
    def __init__(
        self, *, client: httpx.AsyncClient | None = None, sleep: Sleep = asyncio.sleep, **kw: Any
    ) -> None:
        super().__init__(**kw)
        if not self.api_key:
            raise ProviderError("Voyage requires an API key", kind="auth", service=VOYAGE_SERVICE)
        self._client = client or httpx.AsyncClient(timeout=REQUEST_TIMEOUT)
        self._owns_client = client is None
        self._sleep = sleep

    async def chat(self, req: ChatRequest) -> ChatResult:
        raise ProviderError(
            "Voyage answers no chat through this adapter", kind="unavailable", service=VOYAGE_SERVICE
        )

    async def list_models(self) -> list[dict]:
        return []

    async def rerank(self, req: RerankRequest) -> RerankResult:
        body = rerank_body(req)
        started = time.perf_counter()
        response = await self._posted(body)
        wait = parse_headers(response.headers) if response.status_code == RATE_LIMITED else None
        if wait is not None and wait <= RETRY_AFTER_CAP_SECONDS:
            await self._sleep(wait)
            response = await self._posted(body)
        if not response.is_success:
            raise _http_failure(response)
        latency = int((time.perf_counter() - started) * 1000)
        return rerank_result(_payload(response), documents=len(req.documents), latency_ms=latency)

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _posted(self, body: Mapping[str, Any]) -> httpx.Response:
        url = (self.base_url or VOYAGE_API).rstrip("/") + RERANK_PATH
        headers = {"Authorization": f"Bearer {self.api_key}"}
        try:
            return await self._client.post(url, json=dict(body), headers=headers, timeout=REQUEST_TIMEOUT)
        except httpx.TimeoutException:
            raise ProviderError(
                "Voyage did not answer in time", kind="unavailable", retryable=True, service=VOYAGE_SERVICE
            ) from None
        except httpx.HTTPError as error:
            raise ProviderError(
                f"Voyage could not be reached ({type(error).__name__})",
                kind="unavailable",
                retryable=True,
                service=VOYAGE_SERVICE,
            ) from None


def rerank_body(req: RerankRequest) -> dict[str, Any]:
    if not req.query.strip():
        raise ProviderError("A rerank needs a query", kind="bad_request", service=VOYAGE_SERVICE)
    if not 1 <= len(req.documents) <= DOCUMENTS_MAX:
        raise ProviderError(
            f"A rerank takes 1 to {DOCUMENTS_MAX} documents, not {len(req.documents)}",
            kind="bad_request",
            service=VOYAGE_SERVICE,
        )
    return {"query": req.query, "documents": list(req.documents), "model": req.model, "truncation": True}


def rerank_result(payload: Any, *, documents: int, latency_ms: int = 0) -> RerankResult:
    rows = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise _off_contract("no data list")
    scores = tuple(_score(row, documents) for row in rows)
    usage = payload.get("usage")
    tokens = usage.get("total_tokens") if isinstance(usage, dict) else None
    if tokens is not None and (not _is_int(tokens) or tokens < 0):
        raise _off_contract("a token count that is not a whole number")
    return RerankResult(scores=scores, total_tokens=tokens, latency_ms=latency_ms)


def _score(row: Any, documents: int) -> tuple[int, float]:
    index = row.get("index") if isinstance(row, dict) else None
    score = row.get("relevance_score") if isinstance(row, dict) else None
    if not _is_int(index) or not 0 <= index < documents:
        raise _off_contract("an index outside the documents sent")
    if isinstance(score, bool) or not isinstance(score, int | float):
        raise _off_contract("a relevance score that is not a number")
    return index, float(score)


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _payload(response: httpx.Response) -> Any:
    try:
        return response.json()
    except ValueError:
        raise _off_contract("a body that is not JSON") from None


def _http_failure(response: httpx.Response) -> ProviderError:
    kind = failure_kind(response.status_code)
    return ProviderError(
        f"Voyage answered {response.status_code} to rerank",
        kind=kind,
        retryable=kind in RETRYABLE_KINDS,
        status=response.status_code,
        retry_after=parse_headers(response.headers),
        service=VOYAGE_SERVICE,
    )


def _off_contract(what: str) -> ProviderError:
    return ProviderError(f"Voyage answered a rerank with {what}", kind="error", service=VOYAGE_SERVICE)
