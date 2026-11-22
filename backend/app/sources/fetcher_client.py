from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime

import httpx
from pydantic import ValidationError

from app.core.errors import ExternalFailure
from app.research.fetcher import (
    FETCHER_FAILURE_STATUS,
    FETCHER_PATH,
    FETCHER_REFUSED_STATUS,
    FetchedPage,
    FetchFailureBody,
    FetchRefusalBody,
    FetchRefused,
    FetchRequest,
)

from .adapter import Clock, utc_now

__all__ = ["FETCHER_MARGIN_SECONDS", "FETCHER_SERVICE", "FetchRecord", "FetchRecorder", "FetcherClient"]

FETCHER_MARGIN_SECONDS = 5.0
FETCHER_SERVICE = "fetcher"

FetchOutcome = FetchedPage | FetchRefused | ExternalFailure


@dataclass(frozen=True)
class FetchRecord:
    url: str
    fetched_at: datetime
    final_url: str | None = None
    status: int | None = None
    content_type: str | None = None
    bytes: int | None = None
    sha256: str | None = None
    blocked_reason: str | None = None

    @classmethod
    def of(cls, url: str, outcome: FetchOutcome, at: datetime) -> FetchRecord:
        if isinstance(outcome, FetchRefused):
            return cls(url=url, fetched_at=at, final_url=outcome.url, blocked_reason=outcome.reason)
        if isinstance(outcome, ExternalFailure):
            return cls(url=url, fetched_at=at, status=outcome.status)
        return cls(
            url=outcome.url,
            fetched_at=outcome.fetched_at,
            final_url=outcome.final_url,
            status=outcome.status,
            content_type=outcome.content_type,
            bytes=outcome.bytes,
            sha256=outcome.sha256,
        )


FetchRecorder = Callable[[FetchRecord], Awaitable[None]]


class FetcherClient:
    def __init__(
        self,
        base_url: str,
        client: httpx.AsyncClient,
        *,
        record: FetchRecorder | None = None,
        clock: Clock = utc_now,
    ) -> None:
        self.endpoint = base_url.rstrip("/") + FETCHER_PATH
        self.client = client
        self.record = record
        self.clock = clock

    async def fetch(self, request: FetchRequest) -> FetchedPage:
        try:
            response = await self.client.post(
                self.endpoint,
                json=request.model_dump(mode="json"),
                timeout=request.timeout_seconds + FETCHER_MARGIN_SECONDS,
            )
        except httpx.TimeoutException:
            raise _failure("the fetcher did not answer in time", kind="unavailable") from None
        except httpx.HTTPError:
            raise _failure("the fetcher could not be reached", kind="unavailable") from None
        outcome = _outcome_of(response)
        if self.record is not None:
            await self.record(FetchRecord.of(request.url, outcome, self.clock()))
        if isinstance(outcome, FetchedPage):
            return outcome
        raise outcome


def _outcome_of(response: httpx.Response) -> FetchOutcome:
    try:
        if response.status_code == 200:
            return FetchedPage.model_validate_json(response.content)
        if response.status_code == FETCHER_REFUSED_STATUS:
            return FetchRefusalBody.model_validate_json(response.content).refusal()
        if response.status_code == FETCHER_FAILURE_STATUS:
            body = FetchFailureBody.model_validate_json(response.content)
            return ExternalFailure(
                body.message,
                kind=body.kind,
                retryable=body.retryable,
                status=body.status,
                retry_after=body.retry_after,
                service=FETCHER_SERVICE,
            )
    except ValidationError:
        raise _failure(f"the fetcher answered {response.status_code} with a body off the contract") from None
    raise _failure(
        f"the fetcher answered {response.status_code}",
        kind="unavailable" if response.status_code >= 500 else "error",
    )


def _failure(message: str, *, kind: str = "error") -> ExternalFailure:
    return ExternalFailure(message, kind=kind, retryable=kind == "unavailable", service=FETCHER_SERVICE)
