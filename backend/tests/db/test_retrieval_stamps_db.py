import hashlib
import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.models import Chunk, Claim, ClaimSource, Concept, Craft, CraftAlias, Provider, RoutePolicy, Source
from app.research.retrieval import HIDDEN_CLAIM_STATUSES, VISIBLE_SENSITIVITY, KnowledgeQuery
from app.retrieval.hybrid import StoredKnowledgeSearch
from app.retrieval.indexing import embed_pending, embed_written, replace_source_chunks
from app.services.craft_resolver import fill_descriptor_embeddings

from ..craft_fixtures import FixedEmbedder, unit

pytestmark = pytest.mark.db

FIRST_MODEL, SECOND_MODEL = "stamp-test-embedder-a", "stamp-test-embedder-b"
RECIPE = "#ctx1"
TITLED = "title: Vornel Print · Vornel mordant | text: Vornel mordant fixes the red."


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-retrieval-stamps/{name}")


CRAFT, CONCEPT, SOURCE, CLAIM = key("Vornel-Print"), key("concept"), key("source"), key("claim")
QUESTION = "vornel mordant"


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            session = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
            await route_to(session, FIRST_MODEL)
            await _seed(session)
            yield session
            await session.close()
        finally:
            await transaction.rollback()


async def route_to(session: AsyncSession, model: str) -> None:
    embed_routes = select(RoutePolicy.providerId).where(RoutePolicy.task == "EMBED")
    await session.execute(update(Provider).where(Provider.id.in_(embed_routes)).values(enabled=True))
    await session.execute(
        update(RoutePolicy).where(RoutePolicy.task == "EMBED").values(model=model, enabled=True)
    )


async def _seed(session: AsyncSession) -> None:
    session.add(Craft(id=CRAFT, slug="Vornel-Print", name="Vornel Print"))
    await session.flush()
    session.add_all(
        [
            Concept(id=CONCEPT, craftId=CRAFT, type="MATERIAL", name="Vornel mordant"),
            Source(id=SOURCE, kind="BOOK", title="Vornel dyeing"),
        ]
    )
    await session.flush()
    session.add(
        Claim(
            id=CLAIM,
            subjectType="CONCEPT",
            subjectId=CONCEPT,
            predicate="explains",
            text="Vornel mordant fixes the red.",
            evidenceLevel="PROVISIONAL",
            origin="IMPORT",
            embedding=unit(1.0),
        )
    )
    await session.flush()
    session.add(ClaimSource(claimId=CLAIM, sourceId=SOURCE))
    await session.flush()


async def stamp_of(session: AsyncSession, model: type[Claim] | type[Chunk], row_id: uuid.UUID) -> str | None:
    return await session.scalar(select(model.embeddingModel).where(model.id == row_id))


async def test_a_vector_written_without_a_stamp_takes_the_routes_model_without_a_recipe(
    session: AsyncSession,
) -> None:
    assert await stamp_of(session, Claim, CLAIM) == FIRST_MODEL
    await replace_source_chunks(session, SOURCE, "Vornel mordant is ground fine.")
    chunk = await session.scalar(select(Chunk.id).where(Chunk.sourceId == SOURCE))
    assert chunk is not None and await stamp_of(session, Chunk, chunk) is None
    await session.execute(update(Chunk).where(Chunk.id == chunk).values(embedding=unit(1.0)))
    assert await stamp_of(session, Chunk, chunk) == FIRST_MODEL


async def test_a_claim_whose_text_changes_loses_its_vector_and_stamp(session: AsyncSession) -> None:
    await session.execute(
        update(Claim).where(Claim.id == CLAIM).values(text="Vornel mordant fixes the blue.")
    )
    row = (
        await session.execute(select(Claim.embedding, Claim.embeddingModel).where(Claim.id == CLAIM))
    ).one()
    assert row.embedding is None and row.embeddingModel is None
    await session.execute(update(Claim).where(Claim.id == CLAIM).values(levelReason="checked again"))
    assert await stamp_of(session, Claim, CLAIM) is None


async def test_only_vectors_of_the_current_model_rank_and_the_rest_are_embedded_again(
    session: AsyncSession,
) -> None:
    search = StoredKnowledgeSearch(session, embed=FixedEmbedder())
    query = KnowledgeQuery(craft_slug="Vornel-Print", text=QUESTION, mode="HYBRID")
    first = (await search.search(query)).claims
    assert [(hit.claim_id, hit.lexical_rank, hit.vector_rank) for hit in first] == [(CLAIM, 1, 1)]
    await route_to(session, SECOND_MODEL)
    stale = (await search.search(query)).claims
    assert [(hit.claim_id, hit.lexical_rank, hit.vector_rank) for hit in stale] == [(CLAIM, 1, None)]
    counts = await embed_written(session, FixedEmbedder(), claim_ids=[CLAIM], source_ids=[])
    assert counts.claims == 1 and await stamp_of(session, Claim, CLAIM) == SECOND_MODEL + RECIPE
    again = (await search.search(query)).claims
    assert [(hit.claim_id, hit.vector_rank) for hit in again] == [(CLAIM, 1)]
    assert (await embed_written(session, FixedEmbedder(), claim_ids=[CLAIM], source_ids=[])).claims == 0


async def test_a_craft_descriptor_is_embedded_again_only_when_its_text_or_model_changes(
    session: AsyncSession,
) -> None:
    await fill_descriptor_embeddings(session, FixedEmbedder(), batch_size=500)
    stored = (
        await session.execute(select(Craft.descriptorHash, Craft.embeddingModel).where(Craft.id == CRAFT))
    ).one()
    assert stored.descriptorHash == hashlib.sha256(b"Vornel Print").hexdigest()
    assert stored.embeddingModel == FIRST_MODEL + RECIPE
    assert await fill_descriptor_embeddings(session, FixedEmbedder(), batch_size=500) == 0
    session.add(CraftAlias(craftId=CRAFT, alias="Vornel Chhap", aliasNorm="vornel chhap", source="CURATED"))
    await session.flush()
    embed = FixedEmbedder()
    assert await fill_descriptor_embeddings(session, embed, batch_size=500) == 1
    assert embed.calls == [["Vornel Print; Vornel Chhap"]]
    changed = await session.scalar(select(Craft.descriptorHash).where(Craft.id == CRAFT))
    assert changed == hashlib.sha256(b"Vornel Print; Vornel Chhap").hexdigest()


async def test_an_old_recipe_still_ranks_and_runs_renew_it_with_its_title_after_the_missing_vectors(
    session: AsyncSession,
) -> None:
    search = StoredKnowledgeSearch(session, embed=FixedEmbedder())
    query = KnowledgeQuery(craft_slug="Vornel-Print", text=QUESTION, mode="HYBRID")
    assert [(hit.claim_id, hit.vector_rank) for hit in (await search.search(query)).claims] == [(CLAIM, 1)]
    assert (await embed_written(session, FixedEmbedder(), claim_ids=[CLAIM], source_ids=[])).claims == 0
    missing = await session.scalar(
        select(func.count(Claim.id)).where(
            Claim.embedding.is_(None),
            Claim.sensitivity == VISIBLE_SENSITIVITY,
            Claim.status.not_in(HIDDEN_CLAIM_STATUSES),
        )
    )
    embed = FixedEmbedder()
    await embed_pending(session, embed, batch_size=500)
    embedded = [words for call in embed.calls for words in call]
    assert embedded.index(TITLED) == missing
    assert await stamp_of(session, Claim, CLAIM) == FIRST_MODEL + RECIPE
