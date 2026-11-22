from __future__ import annotations

import uuid
from collections.abc import Callable
from contextlib import AbstractAsyncContextManager
from typing import Any

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import WebFetch
from app.sources.fetcher_client import FetchRecord, FetchRecorder

__all__ = ["SessionScope", "web_fetch_recorder", "write_web_fetch"]

SessionScope = Callable[[], AbstractAsyncContextManager[AsyncSession]]


def web_fetch_recorder(scope: SessionScope) -> FetchRecorder:
    async def record(fetch: FetchRecord) -> None:
        async with scope() as session:
            await write_web_fetch(session, fetch)

    return record


async def write_web_fetch(session: AsyncSession, fetch: FetchRecord) -> uuid.UUID:
    values = _columns(fetch)
    first = await session.execute(
        insert(WebFetch)
        .values(values)
        .on_conflict_do_nothing(index_elements=["sha256"])
        .returning(WebFetch.id)
    )
    row_id = first.scalar_one_or_none()
    if row_id is not None:
        return row_id
    again = await session.execute(insert(WebFetch).values(values | {"sha256": None}).returning(WebFetch.id))
    return again.scalar_one()


def _columns(fetch: FetchRecord) -> dict[str, Any]:
    return {
        "url": fetch.url,
        "finalUrl": fetch.final_url,
        "status": fetch.status,
        "contentType": fetch.content_type,
        "bytes": fetch.bytes,
        "sha256": fetch.sha256,
        "fetchedAt": fetch.fetched_at,
        "blockedReason": fetch.blocked_reason,
    }
