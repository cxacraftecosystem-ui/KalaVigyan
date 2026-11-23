from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.models import Source
from app.services.claim_seed import load_seed_claims, seed_claims, seed_id

pytestmark = pytest.mark.db

VAM = "ie:ajrakh:S3"


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            session = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
            yield session
            await session.close()
        finally:
            await transaction.rollback()


def seeded_source(seed_key: str, authors: list[str]) -> dict[str, Any]:
    row = next(source for source in load_seed_claims()["sources"] if source["id"] == seed_key)
    return {"sources": [{**row, "authors": authors}], "concepts": [], "edges": [], "claims": []}


async def authors_of(session: AsyncSession, seed_key: str) -> list[str]:
    found = await session.scalar(select(Source.authors).where(Source.id == seed_id("source", seed_key)))
    assert found is not None
    return list(found)


async def test_a_seeded_source_takes_the_authors_the_seed_now_gives(session: AsyncSession) -> None:
    await seed_claims(session, seeded_source(VAM, ["Victoria and Albert Museum"]))
    assert await authors_of(session, VAM) == ["Victoria and Albert Museum"]


async def test_a_source_not_written_by_the_import_keeps_its_authors(session: AsyncSession) -> None:
    source = seed_id("source", VAM)
    await session.execute(
        update(Source).where(Source.id == source).values(origin="CONTRIBUTION", authors=["Kept"])
    )
    await seed_claims(session, seeded_source(VAM, ["Victoria and Albert Museum"]))
    assert await authors_of(session, VAM) == ["Kept"]
