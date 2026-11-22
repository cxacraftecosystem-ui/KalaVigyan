from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass

import httpx

__all__ = [
    "KEY_CHECK_SECONDS",
    "KEY_NOT_ACCEPTED",
    "KEY_SPENT",
    "PROVIDER_TROUBLED",
    "PROVIDER_UNANSWERED",
    "PROVIDER_UNREACHABLE",
    "KeyCheck",
    "KeyVerdict",
    "checked_get",
    "verdict_of_status",
]

logger = logging.getLogger(__name__)

KEY_CHECK_SECONDS = 6.0
PROVIDER_UNANSWERED = "The provider didn't answer in time. Try again."
PROVIDER_UNREACHABLE = "The provider couldn't be reached. Try again."
KEY_NOT_ACCEPTED = "The provider didn't accept this key."
KEY_SPENT = "The key works, but it has reached its usage limit. Try again later."
PROVIDER_TROUBLED = "The provider had a problem checking this key. Try again later."
REFUSED_KEY_STATUSES = frozenset({401, 403})
SPENT_KEY_STATUS = 429


@dataclass(frozen=True)
class KeyVerdict:
    ok: bool
    error: str | None = None


KeyCheck = Callable[[httpx.AsyncClient, str], Awaitable[KeyVerdict]]


def verdict_of_status(status: int) -> KeyVerdict:
    if 200 <= status < 300:
        return KeyVerdict(ok=True)
    if status in REFUSED_KEY_STATUSES:
        return KeyVerdict(ok=False, error=KEY_NOT_ACCEPTED)
    if status == SPENT_KEY_STATUS:
        return KeyVerdict(ok=False, error=KEY_SPENT)
    return KeyVerdict(ok=False, error=PROVIDER_TROUBLED)


async def checked_get(
    client: httpx.AsyncClient,
    url: str,
    *,
    headers: Mapping[str, str] | None = None,
    params: Mapping[str, str] | None = None,
) -> KeyVerdict:
    try:
        response = await client.get(
            url, headers=dict(headers or {}), params=dict(params or {}), timeout=KEY_CHECK_SECONDS
        )
    except httpx.TimeoutException:
        return KeyVerdict(ok=False, error=PROVIDER_UNANSWERED)
    except httpx.HTTPError as error:
        logger.warning("key check network error", extra={"error": type(error).__name__})
        return KeyVerdict(ok=False, error=PROVIDER_UNREACHABLE)
    return verdict_of_status(response.status_code)
