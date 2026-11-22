from __future__ import annotations

from fastapi import HTTPException, status

from app.core.rate_limit import retry_after_value

__all__ = ["refuse_when_throttled", "too_many_requests"]


def too_many_requests(detail: str, wait_seconds: float | None = None) -> HTTPException:
    headers = None if wait_seconds is None else {"Retry-After": retry_after_value(wait_seconds)}
    return HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail, headers)


def refuse_when_throttled(attempt: tuple[bool, float], detail: str) -> None:
    allowed, wait_seconds = attempt
    if not allowed:
        raise too_many_requests(detail, wait_seconds)
