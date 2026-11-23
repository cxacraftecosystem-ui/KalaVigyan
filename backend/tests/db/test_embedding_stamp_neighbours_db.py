import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.models import Claim, Concept, Craft, KnowledgePiece as PieceRow
from app.retrieval.indexing import embed_pieces
from app.services.candidate_store import CRAFT, FactSubject, SqlHeldFacts

from ..craft_fixtures import unit
from .test_knowledge_pieces_db import failing_embedder, fixed_embedder, kept, store_for
from .test_retrieval_stamps_db import route_to

pytestmark = pytest.mark.db

MODEL = "stamp-test-embedder-a"
RETIRED = "retired-embedder#ctx1"


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-embedding-stamp-neighbours/{name}")


CRAFT_ID, CONCEPT, CLAIM = key("Quillan-Print"), key("concept"), key("claim")


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            session = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
            await route_to(session, MODEL)
            yield session
            await session.close()
        finally:
            await transaction.rollback()


async def held_claim(session: AsyncSession) -> FactSubject:
    session.add(Craft(id=CRAFT_ID, slug="Quillan-Print", name="Quillan Print"))
    await session.flush()
    session.add(Concept(id=CONCEPT, craftId=CRAFT_ID, type="MATERIAL", name="Quillan mordant"))
    await session.flush()
    session.add(
        Claim(
            id=CLAIM,
            subjectType="CONCEPT",
            subjectId=CONCEPT,
            predicate="explains",
            text="Quillan mordant fixes the red.",
            evidenceLevel="PROVISIONAL",
            origin="IMPORT",
            status="APPROVED",
            embedding=unit(1.0),
        )
    )
    await session.flush()
    return FactSubject(kind=CRAFT, name="Quillan Print", slug="Quillan-Print", craft_id=CRAFT_ID)


async def test_a_gate_compares_a_fact_only_with_held_facts_of_the_current_embedding_model(
    session: AsyncSession,
) -> None:
    held = SqlHeldFacts(session, await held_claim(session))
    assert [fact.id for fact in await held.nearest(None, unit(1.0), 5)] == [CLAIM]
    await session.execute(update(Claim).where(Claim.id == CLAIM).values(embeddingModel=RETIRED))
    assert await held.nearest(None, unit(1.0), 5) == []


async def test_a_piece_vector_carries_the_current_model_and_another_model_s_vector_is_renewed(
    session: AsyncSession,
) -> None:
    _, row = await kept(session, store_for(session, embed=failing_embedder))
    assert await embed_pieces(session, fixed_embedder, piece_ids=[row.id]) == 1
    current = await session.scalar(select(func.kv_embedding_model()))
    stamp = await session.scalar(select(PieceRow.embeddingModel).where(PieceRow.id == row.id))
    assert stamp == current and current is not None and current.startswith(MODEL)
    assert await embed_pieces(session, fixed_embedder, piece_ids=[row.id]) == 0
    await session.execute(update(PieceRow).where(PieceRow.id == row.id).values(embeddingModel=RETIRED))
    assert await embed_pieces(session, fixed_embedder, piece_ids=[row.id]) == 1
