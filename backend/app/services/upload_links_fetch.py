from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from pydantic import ValidationError

from app.core.config import get_settings
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

__all__ = ["FETCH_MARGIN_SECONDS", "PictureFetcherClient", "picture_fetcher"]

FETCH_MARGIN_SECONDS = 5.0
SERVICE = "fetcher"
REFUSED = "The picture's link was refused: {why}"
UNREAD = "The picture's link could not be read: {why}"
SLOW = "The picture's link did not answer in time"
UNREACHABLE = "The fetcher could not be reached"


class PictureFetcherClient:
    def __init__(self, base_url: str, client: httpx.AsyncClient) -> None:
        self.endpoint = base_url.rstrip("/") + PICTURE_FETCH_PATH
        self.client = client

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
        return _picture_from(url, response)


@asynccontextmanager
async def picture_fetcher() -> AsyncIterator[PictureFetcher]:
    async with httpx.AsyncClient() as client:
        yield PictureFetcherClient(get_settings().fetcher_url, client)


def _picture_from(url: str, response: httpx.Response) -> FetchedPicture:
    try:
        if response.status_code == FETCHER_REFUSED_STATUS:
            refusal = FetchRefusalBody.model_validate_json(response.content)
            raise InvalidInput(REFUSED.format(why=refusal.detail or refusal.reason))
        if response.status_code == FETCHER_FAILURE_STATUS:
            failure = FetchFailureBody.model_validate_json(response.content)
            raise InvalidInput(UNREAD.format(why=failure.message))
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
