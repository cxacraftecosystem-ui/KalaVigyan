import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.models import Claim, ClaimSource, Concept, Craft

__all__ = ["CONCEPT", "CRAFT", "SLUG", "Cite", "fact", "fact_text", "key", "seeded_session"]

SLUG = "Quote-Visibility-Test-Craft"


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-quote-visibility/{name}")


CRAFT, CONCEPT = key("craft"), key("concept")


@dataclass(frozen=True)
class Cite:
    source_id: uuid.UUID
    quote: str | None
    check: str = "PASS"
    chunk_id: uuid.UUID | None = None
    locator: str | None = None


def fact_text(claim_id: uuid.UUID) -> str:
    return f"Alum fixes the red, says fact {claim_id.hex[:8]}."


async def seeded_session() -> AsyncIterator[AsyncSession]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            session = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
            session.add(Craft(id=CRAFT, slug=SLUG, name="Quote Visibility Test Craft"))
            await session.flush()
            session.add(Concept(id=CONCEPT, craftId=CRAFT, type="MATERIAL", name="Alum"))
            await session.flush()
            yield session
            await session.close()
        finally:
            await transaction.rollback()


async def fact(session: AsyncSession, claim_id: uuid.UUID, *cites: Cite) -> None:
    session.add(
        Claim(
            id=claim_id,
            subjectType="CONCEPT",
            subjectId=CONCEPT,
            predicate="states",
            text=fact_text(claim_id),
            evidenceLevel="PROVISIONAL",
            origin="IMPORT",
        )
    )
    await session.flush()
    session.add_all(
        ClaimSource(
            claimId=claim_id,
            sourceId=cite.source_id,
            chunkId=cite.chunk_id,
            quote=cite.quote,
            locator=cite.locator,
            quoteCheck=cite.check if cite.quote else "NA",
        )
        for cite in cites
    )
    await session.flush()
