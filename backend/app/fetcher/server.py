from __future__ import annotations

import asyncio
import logging

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.core.errors import ExternalFailure
from app.research.fetcher import (
    FETCHER_FAILURE_STATUS,
    FETCHER_HEALTH_PATH,
    FETCHER_PATH,
    FETCHER_REFUSED_STATUS,
    Fetcher,
    FetchFailureBody,
    FetchRefusalBody,
    FetchRefused,
    FetchRequest,
)

from .client_documents import ClientDocumentFetch, add_client_document_route
from .pictures import PictureFetch, add_picture_route

__all__ = ["FETCH_CONCURRENCY", "create_app"]

FETCH_CONCURRENCY = 8

logger = logging.getLogger("kalavigyan.fetcher")


def create_app(fetcher: Fetcher) -> FastAPI:
    app = FastAPI(title="KalaVigyan fetcher", docs_url=None, redoc_url=None, openapi_url=None)
    slots = asyncio.Semaphore(FETCH_CONCURRENCY)
    add_picture_route(app, PictureFetch.build())
    add_client_document_route(app, ClientDocumentFetch.build())

    @app.get(FETCHER_HEALTH_PATH)
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post(FETCHER_PATH)
    async def fetch(request: FetchRequest) -> JSONResponse:
        async with slots:
            return await _answer(fetcher, request)

    return app


async def _answer(fetcher: Fetcher, request: FetchRequest) -> JSONResponse:
    try:
        page = await fetcher.fetch(request)
    except FetchRefused as refusal:
        logger.info("fetch refused: %s", refusal.reason)
        body = FetchRefusalBody.of(refusal)
        return JSONResponse(body.model_dump(mode="json"), status_code=FETCHER_REFUSED_STATUS)
    except ExternalFailure as failure:
        logger.info("fetch failed: %s", failure.kind)
        body = FetchFailureBody(
            kind=failure.kind,
            message=str(failure)[:500] or failure.kind,
            retryable=failure.retryable,
            status=failure.status,
            retry_after=failure.retry_after,
        )
        return JSONResponse(
            body.model_dump(mode="json", exclude_none=True), status_code=FETCHER_FAILURE_STATUS
        )
    return JSONResponse(page.model_dump(mode="json"))
