import hashlib
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.models import WebFetch
from app.services.web_fetches import web_fetch_recorder, write_web_fetch
from app.sources.fetcher_client import FetchRecord

pytestmark = pytest.mark.db

ARTICLE = "https://crafts.example.org/test-web-fetches/ajrakh"
MIRROR = "https://mirror.example.net/test-web-fetches/ajrakh"
INTRANET = "https://intranet.example.org/test-web-fetches/admin"
BODY_HASH = hashlib.sha256(b"test-web-fetches: the same page bytes").hexdigest()
FETCHED = datetime(2026, 11, 22, 8, 15, tzinfo=UTC)


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            opened = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
            yield opened
            await opened.close()
        finally:
            await transaction.rollback()


def read_page(url: str) -> FetchRecord:
    return FetchRecord(
        url=url,
        fetched_at=FETCHED,
        final_url=url,
        status=200,
        content_type="text/html",
        bytes=2048,
        sha256=BODY_HASH,
    )


async def row(session: AsyncSession, row_id: uuid.UUID) -> WebFetch:
    found = await session.scalar(select(WebFetch).where(WebFetch.id == row_id))
    assert found is not None
    return found


async def test_a_read_page_is_one_row_with_what_the_fetch_returned(session: AsyncSession) -> None:
    written = await row(session, await write_web_fetch(session, read_page(ARTICLE)))
    assert (
        written.url,
        written.finalUrl,
        written.status,
        written.contentType,
        written.bytes,
        written.sha256,
        written.fetchedAt,
        written.blockedReason,
    ) == (ARTICLE, ARTICLE, 200, "text/html", 2048, BODY_HASH, FETCHED, None)


async def test_the_same_bytes_fetched_again_are_a_second_row_and_the_hash_stays_on_the_first(
    session: AsyncSession,
) -> None:
    first = await write_web_fetch(session, read_page(ARTICLE))
    second = await write_web_fetch(session, read_page(MIRROR))
    assert first != second
    kept, again = await row(session, first), await row(session, second)
    assert (kept.url, kept.sha256) == (ARTICLE, BODY_HASH)
    assert (again.url, again.sha256, again.status, again.bytes) == (MIRROR, None, 200, 2048)


async def test_a_refused_fetch_is_a_row_with_its_reason_through_the_recorder(session: AsyncSession) -> None:
    @asynccontextmanager
    async def scope() -> AsyncIterator[AsyncSession]:
        yield session

    refused = FetchRecord(
        url=ARTICLE, fetched_at=FETCHED, final_url=INTRANET, blocked_reason="PRIVATE_ADDRESS"
    )
    await web_fetch_recorder(scope)(refused)
    written = await session.scalar(select(WebFetch).where(WebFetch.finalUrl == INTRANET))
    assert written is not None
    assert (written.url, written.status, written.sha256, written.blockedReason) == (
        ARTICLE,
        None,
        None,
        "PRIVATE_ADDRESS",
    )
