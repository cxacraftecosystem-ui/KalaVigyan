import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.models import Claim, ClaimSource, Concept, Source
from app.retrieval.statements import CraftScope, claim_conditions, facet_disciplines
from app.services import knowledge_view

pytestmark = pytest.mark.db

CRAFT = "Kutch-Ajrakh"
PLACE = uuid.UUID("f4ce7000-0000-4000-8000-000000000001")
HISTORY_CLAIM = uuid.UUID("f4ce7000-0000-4000-8000-000000000002")
SOURCE = uuid.UUID("f4ce7000-0000-4000-8000-000000000003")
HISTORY_TEXT = "Dhamadka was settled by Khatri printers who came from Sindh in the sixteenth century."


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


async def place_history(session: AsyncSession) -> CraftScope:
    craft = await knowledge_view.resolve_craft(session, CRAFT)
    assert craft is not None
    session.add(Concept(id=PLACE, craftId=craft.id, type="ENVIRONMENTAL_CONDITION", name="Dhamadka"))
    session.add(Source(id=SOURCE, kind="BOOK", title="A history of Kutch printing"))
    await session.flush()
    session.add(
        Claim(
            id=HISTORY_CLAIM,
            subjectType="CONCEPT",
            subjectId=PLACE,
            predicate="states",
            text=HISTORY_TEXT,
            evidenceLevel="PROVISIONAL",
            origin="IMPORT",
            status="APPROVED",
            field="HISTORY",
        )
    )
    await session.flush()
    session.add(ClaimSource(claimId=HISTORY_CLAIM, sourceId=SOURCE, quote=HISTORY_TEXT, quoteCheck="PASS"))
    await session.flush()
    return CraftScope(craft.id, craft.subCategoryId)


async def found(session: AsyncSession, scope: CraftScope, facets: tuple[str, ...]) -> bool:
    statement = select(Claim.id).where(
        Claim.id == HISTORY_CLAIM, *claim_conditions(scope, mode="DEEP", facets=facets)
    )
    return await session.scalar(statement) is not None


def test_a_facet_maps_to_the_discipline_its_concept_type_belongs_to() -> None:
    assert facet_disciplines(("HISTORICAL_CONTEXT", "MATERIAL", "TOOL", "OUTCOME")) == [
        "HISTORY",
        "MATERIALS",
    ]
    assert facet_disciplines(()) == []


async def test_a_history_facet_finds_a_history_claim_about_a_place(session: AsyncSession) -> None:
    scope = await place_history(session)
    assert await found(session, scope, ("HISTORICAL_CONTEXT",))
    assert await found(session, scope, ("ENVIRONMENTAL_CONDITION",))
    assert not await found(session, scope, ("MECHANISM",))
