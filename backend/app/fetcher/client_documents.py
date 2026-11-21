from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response

from app.core.errors import ExternalFailure
from app.research.fetcher import (
    FETCHER_FAILURE_STATUS,
    FETCHER_REFUSED_STATUS,
    FetchFailureBody,
    FetchRefusalBody,
    FetchRefused,
)
from app.research.oauth_client_documents import (
    CLIENT_DOCUMENT_ACCEPT,
    CLIENT_DOCUMENT_CACHE_HEADER,
    CLIENT_DOCUMENT_FETCH_PATH,
    CLIENT_DOCUMENT_MAX_BYTES,
    CLIENT_DOCUMENT_TIMEOUT_SECONDS,
    ClientDocumentRequest,
)

from .targets import checked_target
from .transport import Hop, PinnedHttp, remote_failure

__all__ = ["CLIENT_DOCUMENT_CONCURRENCY", "ClientDocumentFetch", "add_client_document_route"]

CLIENT_DOCUMENT_CONCURRENCY = 4
JSON_TYPE = "application/json"
NOT_FOLLOWED = "a client ID metadata document is read at its own address only, never through a redirect"

logger = logging.getLogger("kalavigyan.fetcher")


@dataclass
class ClientDocumentFetch:
    http: PinnedHttp
    timeout: float = CLIENT_DOCUMENT_TIMEOUT_SECONDS

    @classmethod
    def build(cls) -> ClientDocumentFetch:
        return cls(PinnedHttp())

    async def fetch(self, url: str) -> Hop:
        target = checked_target(url)
        try:
            async with asyncio.timeout(self.timeout):
                hop = await self.http.get(
                    target,
                    max_bytes=CLIENT_DOCUMENT_MAX_BYTES,
                    timeout=self.timeout,
                    accept=CLIENT_DOCUMENT_ACCEPT,
                )
        except TimeoutError:
            raise FetchRefused(url, "TIME_LIMIT", f"not done in {self.timeout:g} seconds") from None
        if hop.is_redirect:
            raise FetchRefused(url, "TOO_MANY_REDIRECTS", NOT_FOLLOWED)
        if hop.status != 200:
            raise remote_failure(hop)
        return hop


def add_client_document_route(app: FastAPI, documents: ClientDocumentFetch) -> None:
    slots = asyncio.Semaphore(CLIENT_DOCUMENT_CONCURRENCY)

    @app.post(CLIENT_DOCUMENT_FETCH_PATH)
    async def fetch_client_document(request: ClientDocumentRequest) -> Response:
        async with slots:
            return await _answer(documents, request)


async def _answer(documents: ClientDocumentFetch, request: ClientDocumentRequest) -> Response:
    try:
        hop = await documents.fetch(request.url)
    except FetchRefused as refusal:
        logger.info("client document refused: %s", refusal.reason)
        body = FetchRefusalBody.of(refusal)
        return JSONResponse(body.model_dump(mode="json"), status_code=FETCHER_REFUSED_STATUS)
    except ExternalFailure as failure:
        logger.info("client document failed: %s", failure.kind)
        failed = FetchFailureBody(
            kind=failure.kind,
            message=str(failure)[:500] or failure.kind,
            retryable=failure.retryable,
            status=failure.status,
        )
        return JSONResponse(
            failed.model_dump(mode="json", exclude_none=True), status_code=FETCHER_FAILURE_STATUS
        )
    headers = {CLIENT_DOCUMENT_CACHE_HEADER: hop.cache_control} if hop.cache_control else {}
    return Response(hop.body, media_type=JSON_TYPE, headers=headers)
