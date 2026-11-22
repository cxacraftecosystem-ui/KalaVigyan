from __future__ import annotations

from typing import Any

from fastapi import Depends, Request, Response
from starlette.requests import HTTPConnection

from app.core.deps import get_optional_user
from app.core.http_cache import (
    PRIVATE_NO_CACHE,
    PUBLIC_READ_CACHE,
    body_version,
    not_modified,
    revalidation_headers,
)
from app.core.rate_limit import public_asset_attempt, public_read_attempt
from app.core.roles import LOWEST_ROLE
from app.core.throttle_refusal import refuse_when_throttled
from app.models import User
from app.research.retrieval import chunk_acls_for

__all__ = [
    "READER_VARY",
    "THROTTLED_DETAIL",
    "cached_read",
    "counted_anonymous_read",
    "public_asset_reader",
    "public_reader",
    "read_headers",
    "reader_cache",
    "reading_acls",
    "reading_role",
    "unchanged_read",
]

READER_VARY = "Authorization"
THROTTLED_DETAIL = "Many pages were read from this address in the last few minutes. Wait a little, or sign in, and try again."


async def public_reader(
    connection: HTTPConnection, user: User | None = Depends(get_optional_user)
) -> User | None:
    if user is not None:
        return user
    _refuse_when_spent(await public_read_attempt(connection))
    return None


async def counted_anonymous_read(connection: HTTPConnection) -> None:
    _refuse_when_spent(await public_read_attempt(connection))


async def public_asset_reader(
    connection: HTTPConnection, user: User | None = Depends(get_optional_user)
) -> User | None:
    if user is not None:
        return user
    _refuse_when_spent(await public_asset_attempt(connection))
    return None


def reading_role(reader: User | None) -> User | str:
    return LOWEST_ROLE if reader is None else reader


def reading_acls(reader: User | None) -> tuple[str, ...]:
    return chunk_acls_for(reader)


def reader_cache(reader: User | None) -> str:
    return PUBLIC_READ_CACHE if reader is None else PRIVATE_NO_CACHE


def read_headers(reader: User | None, version: str) -> dict[str, str]:
    return {**revalidation_headers(version, cache_control=reader_cache(reader)), "Vary": READER_VARY}


def unchanged_read(request: Request, reader: User | None, version: str) -> Response | None:
    answer = not_modified(request, version, cache_control=reader_cache(reader))
    if answer is not None:
        answer.headers["Vary"] = READER_VARY
    return answer


def cached_read(
    request: Request, response: Response, reader: User | None, body: Any, *, version: str | None = None
) -> Any:
    stamp = version or body_version(body)
    unchanged = unchanged_read(request, reader, stamp)
    if unchanged is not None:
        return unchanged
    response.headers.update(read_headers(reader, stamp))
    return body


def _refuse_when_spent(attempt: tuple[bool, float]) -> None:
    refuse_when_throttled(attempt, THROTTLED_DETAIL)
