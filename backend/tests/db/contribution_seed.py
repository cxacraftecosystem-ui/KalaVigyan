import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.models import Concept, Craft, CraftCategory, CraftSubCategory, User
from app.research.knowledge_writes import FactProposal
from app.services.fact_proposals import ProposalAdapters

from ..craft_fixtures import unit
from ..knowledge_writes.fakes import PAGE_URL, QUOTE, STATEMENT, FakeEmbedder, FakeFetcher, FakeJudge, page

__all__ = [
    "CONCEPT",
    "CRAFT",
    "NOW",
    "SLUG",
    "adapters",
    "fact",
    "key",
    "person",
    "same_session",
    "seeded_session",
]

NOW = datetime(2026, 11, 20, 9, 0, tzinfo=UTC)
SLUG = "Contribution-Queue-Test-Craft"


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-contribution-queue/{name}")


CATEGORY, FAMILY, CRAFT, CONCEPT = key("category"), key("family"), key("craft"), key("concept")


async def seeded_session() -> AsyncIterator[AsyncSession]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            session = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
            await _seed(session)
            yield session
            await session.close()
        finally:
            await transaction.rollback()


@asynccontextmanager
async def same_session(session: AsyncSession) -> AsyncIterator[AsyncSession]:
    yield session


async def person(session: AsyncSession, role: str) -> User:
    token = uuid.uuid4()
    user = User(
        id=token, name=f"{role.title()} {token.hex[:4]}", email=f"{token.hex[:12]}@example.org", role=role
    )
    session.add(user)
    await session.flush()
    return user


def fact(statement: str = STATEMENT, **changes: Any) -> FactProposal:
    body: dict[str, Any] = {
        "subject": {"kind": "craft", "slug": SLUG},
        "field": "PROCESS",
        "statement": statement,
        "sources": [
            {"url": PAGE_URL, "title": "Indigo in Ajrakh", "quotes": [{"text": QUOTE, "locator": "p. 2"}]}
        ],
    }
    return FactProposal.model_validate(body | changes)


def adapters(*replies: dict[str, Any], fetched: Any = None) -> ProposalAdapters:
    return ProposalAdapters(
        fetcher=FakeFetcher({PAGE_URL: fetched if fetched is not None else page()}),
        embed=FakeEmbedder(unit(1.0)),
        judge=FakeJudge(*replies),
    )


async def _seed(session: AsyncSession) -> None:
    session.add(
        CraftCategory(id=CATEGORY, slug="contribution-queue-category", name="Queue Category", sortOrder=996)
    )
    await session.flush()
    session.add(
        CraftSubCategory(
            id=FAMILY, slug="contribution-queue-family", name="Queue", categoryId=CATEGORY, sortOrder=1
        )
    )
    await session.flush()
    session.add(Craft(id=CRAFT, slug=SLUG, name="Contribution Queue Test Craft", subCategoryId=FAMILY))
    await session.flush()
    session.add(
        Concept(id=CONCEPT, craftId=CRAFT, type="ARTISAN_ACTION", name="Contribution Queue Test Craft")
    )
    await session.flush()
