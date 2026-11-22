from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response

from app.core.errors import ExternalFailure, InvalidInput
from app.research.fetcher import (
    FETCH_MAX_REDIRECTS,
    FETCHER_FAILURE_STATUS,
    FETCHER_REFUSED_STATUS,
    FetchFailureBody,
    FetchRefusalBody,
    FetchRefused,
)
from app.research.image_intake_fetch import (
    FINAL_URL_HEADER,
    PICTURE_FETCH_ACCEPT,
    PICTURE_FETCH_PATH,
    PICTURE_FETCH_TIMEOUT_SECONDS,
    PictureFetchRequest,
)
from app.research.image_intake_types import received_type

from .targets import Target, checked_target, redirect_target
from .transport import Hop, PinnedHttp, PinnedSession, remote_failure

__all__ = ["PICTURE_FETCH_CONCURRENCY", "FoundPicture", "PictureFetch", "add_picture_route"]

PICTURE_FETCH_CONCURRENCY = 4

logger = logging.getLogger("kalavigyan.fetcher")


@dataclass(frozen=True)
class FoundPicture:
    final_url: str
    mime: str
    data: bytes


@dataclass
class PictureFetch:
    http: PinnedHttp

    @classmethod
    def build(cls) -> PictureFetch:
        return cls(PinnedHttp())

    async def fetch(self, request: PictureFetchRequest) -> FoundPicture:
        try:
            async with asyncio.timeout(PICTURE_FETCH_TIMEOUT_SECONDS):
                hop = await self._followed(request)
        except TimeoutError:
            raise FetchRefused(
                request.url, "TIME_LIMIT", f"not done in {PICTURE_FETCH_TIMEOUT_SECONDS:g} seconds"
            ) from None
        try:
            mime = received_type(hop.body)
        except InvalidInput:
            shown = hop.content_type or "no type"
            raise FetchRefused(
                request.url, "CONTENT_TYPE", f"the link gives {shown}, not a picture"
            ) from None
        return FoundPicture(final_url=hop.target.url, mime=mime, data=hop.body)

    async def _followed(self, request: PictureFetchRequest) -> Hop:
        target = checked_target(request.url)
        async with self.http.session() as hops:
            hop = await _hop(hops, target, request)
            for _ in range(FETCH_MAX_REDIRECTS):
                if not hop.is_redirect:
                    break
                if not hop.location:
                    raise ExternalFailure(f"{target.host} redirected without a location", service="fetcher")
                target = redirect_target(target, hop.location)
                hop = await _hop(hops, target, request)
        if hop.is_redirect:
            raise FetchRefused(request.url, "TOO_MANY_REDIRECTS", f"more than {FETCH_MAX_REDIRECTS}")
        if not hop.is_success:
            raise remote_failure(hop)
        return hop


async def _hop(hops: PinnedSession, target: Target, request: PictureFetchRequest) -> Hop:
    return await hops.get(
        target,
        max_bytes=request.max_bytes,
        timeout=PICTURE_FETCH_TIMEOUT_SECONDS,
        accept=PICTURE_FETCH_ACCEPT,
    )


def add_picture_route(app: FastAPI, pictures: PictureFetch) -> None:
    slots = asyncio.Semaphore(PICTURE_FETCH_CONCURRENCY)

    @app.post(PICTURE_FETCH_PATH)
    async def fetch_picture(request: PictureFetchRequest) -> Response:
        async with slots:
            return await _answer(pictures, request)


async def _answer(pictures: PictureFetch, request: PictureFetchRequest) -> Response:
    try:
        found = await pictures.fetch(request)
    except FetchRefused as refusal:
        logger.info("picture fetch refused: %s", refusal.reason)
        body = FetchRefusalBody.of(refusal)
        return JSONResponse(body.model_dump(mode="json"), status_code=FETCHER_REFUSED_STATUS)
    except ExternalFailure as failure:
        logger.info("picture fetch failed: %s", failure.kind)
        failed = FetchFailureBody(
            kind=failure.kind,
            message=str(failure)[:500] or failure.kind,
            retryable=failure.retryable,
            status=failure.status,
            retry_after=failure.retry_after,
        )
        return JSONResponse(
            failed.model_dump(mode="json", exclude_none=True), status_code=FETCHER_FAILURE_STATUS
        )
    return Response(found.data, media_type=found.mime, headers={FINAL_URL_HEADER: found.final_url})
