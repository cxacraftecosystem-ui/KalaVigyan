from __future__ import annotations

import hashlib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime

import httpx
from pydantic import ValidationError

from app.core.config import get_settings
from app.core.db import session_scope
from app.core.errors import ExternalFailure, InvalidInput
from app.research.fetcher import (
    FETCHER_FAILURE_STATUS,
    FETCHER_REFUSED_STATUS,
    FetchFailureBody,
    FetchRefusalBody,
)
from app.research.image_intake_fetch import (
    FINAL_URL_HEADER,
    PICTURE_FETCH_PATH,
    PICTURE_FETCH_TIMEOUT_SECONDS,
    FetchedPicture,
    PictureFetcher,
    PictureFetchRequest,
)
from app.sources.adapter import Clock, utc_now
from app.sources.fetcher_client import FetchRecord, FetchRecorder

from .web_fetches import web_fetch_recorder

__all__ = ["FETCH_MARGIN_SECONDS", "PictureFetcherClient", "picture_fetcher"]

FETCH_MARGIN_SECONDS = 5.0
SERVICE = "fetcher"
REFUSED = "The picture's link was refused: {why}"
UNREAD = "The picture's link could not be read: {why}"
SLOW = "The picture's link did not answer in time"
UNREACHABLE = "The fetcher could not be reached"

PictureAnswer = FetchedPicture | FetchRefusalBody | FetchFailureBody


class PictureFetcherClient:
    def __init__(
        self,
        base_url: str,
        client: httpx.AsyncClient,
        *,
        record: FetchRecorder | None = None,
        clock: Clock = utc_now,
    ) -> None:
        self.endpoint = base_url.rstrip("/") + PICTURE_FETCH_PATH
        self.client = client
        self.record = record
        self.clock = clock

    async def fetch_picture(self, url: str) -> FetchedPicture:
        request = PictureFetchRequest(url=url)
        try:
            response = await self.client.post(
                self.endpoint,
                json=request.model_dump(mode="json"),
                timeout=PICTURE_FETCH_TIMEOUT_SECONDS + FETCH_MARGIN_SECONDS,
            )
        except httpx.TimeoutException:
            raise InvalidInput(SLOW) from None
        except httpx.HTTPError:
            raise ExternalFailure(UNREACHABLE, kind="unavailable", retryable=True, service=SERVICE) from None
        answer = _answer_of(url, response)
        if self.record is not None:
            await self.record(_record_of(url, answer, self.clock()))
        if isinstance(answer, FetchRefusalBody):
            raise InvalidInput(REFUSED.format(why=answer.detail or answer.reason))
        if isinstance(answer, FetchFailureBody):
            raise InvalidInput(UNREAD.format(why=answer.message))
        return answer


@asynccontextmanager
async def picture_fetcher() -> AsyncIterator[PictureFetcher]:
    async with httpx.AsyncClient() as client:
        yield PictureFetcherClient(
            get_settings().fetcher_url, client, record=web_fetch_recorder(session_scope)
        )


def _answer_of(url: str, response: httpx.Response) -> PictureAnswer:
    try:
        if response.status_code == FETCHER_REFUSED_STATUS:
            return FetchRefusalBody.model_validate_json(response.content)
        if response.status_code == FETCHER_FAILURE_STATUS:
            return FetchFailureBody.model_validate_json(response.content)
    except ValidationError:
        raise ExternalFailure(
            f"the fetcher answered {response.status_code} with a body off the contract", service=SERVICE
        ) from None
    if response.status_code != 200:
        raise ExternalFailure(f"the fetcher answered {response.status_code}", service=SERVICE)
    return FetchedPicture(
        url=url,
        final_url=response.headers.get(FINAL_URL_HEADER, url),
        content_type=response.headers.get("content-type", ""),
        data=response.content,
    )


def _record_of(url: str, answer: PictureAnswer, at: datetime) -> FetchRecord:
    if isinstance(answer, FetchRefusalBody):
        return FetchRecord(url=url, fetched_at=at, final_url=answer.url, blocked_reason=answer.reason)
    if isinstance(answer, FetchFailureBody):
        return FetchRecord(url=url, fetched_at=at, status=answer.status)
    return FetchRecord(
        url=url,
        fetched_at=at,
        final_url=answer.final_url,
        status=200,
        content_type=answer.content_type,
        bytes=len(answer.data),
        sha256=hashlib.sha256(answer.data).hexdigest(),
    )
