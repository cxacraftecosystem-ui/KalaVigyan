from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ExternalFailure
from app.models import Chunk, Claim, Source
from app.retrieval.indexing import replace_source_chunks
from app.services.answering import AnswerAsk
from app.services.craft_resolver import CraftIndexStore
from app.services.research_write_back import store_live_research

from ..craft_fixtures import FixedEmbedder
from .write_back_seed import (
    ABSTRACT_ID,
    ALUM_CONCEPT,
    ANSWER,
    FIGURE_KEY,
    FIGURE_QUOTE,
    FIGURE_TEXT,
    ZELVAR,
    answer,
    answer_store,
    expected_claim_id,
    kept_answer,
    key,
    said,
    seeded_session,
    zelvar_pack,
)

pytestmark = pytest.mark.db


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in seeded_session():
        yield opened


class FailingEmbedder:
    async def __call__(self, texts: list[str]) -> list[list[float]]:
        raise ExternalFailure("embedding route timed out", kind="unavailable", service="embeddings")


async def test_a_write_back_embeds_only_the_rows_it_wrote(session: AsyncSession) -> None:
    unrelated, waiting = key("unrelated-source"), key("waiting-claim")
    session.add(Source(id=unrelated, kind="PAPER", title="Paper no answer read"))
    session.add(
        Claim(
            id=waiting,
            subjectType="CONCEPT",
            subjectId=ALUM_CONCEPT,
            predicate="states",
            text="A seeded claim still waiting for its vector.",
            evidenceLevel="REVIEWED",
            origin="IMPORT",
        )
    )
    await session.flush()
    await replace_source_chunks(session, unrelated, "Text that no answer in this test read.")
    embedder = FixedEmbedder()
    stored = await store_live_research(
        session,
        zelvar_pack(),
        answer(said(FIGURE_TEXT, ABSTRACT_ID, FIGURE_QUOTE)),
        embed=embedder,
        found_by="ANSWER",
        index=CraftIndexStore(),
        answer_id=ANSWER,
    )
    assert stored.embedded.claims == 1
    assert stored.embedding_error is None
    assert (await session.get(Claim, waiting)).embedding is None
    left = list(await session.scalars(select(Chunk.embedding).where(Chunk.sourceId == unrelated)))
    assert left == [None]
    embedded_texts = [text for call in embedder.calls for text in call]
    assert not any(
        "waiting for its vector" in text or "no answer in this test" in text for text in embedded_texts
    )


async def test_a_failed_embedding_keeps_the_written_claims_for_later(session: AsyncSession) -> None:
    stored = await store_live_research(
        session,
        zelvar_pack(),
        answer(said(FIGURE_TEXT, ABSTRACT_ID, FIGURE_QUOTE)),
        embed=FailingEmbedder(),
        found_by="ANSWER",
        index=CraftIndexStore(),
        answer_id=ANSWER,
    )
    claim_id = expected_claim_id(FIGURE_KEY)
    assert [(r.claim_id, r.created) for r in stored.results] == [(claim_id, True)]
    assert (stored.embedded.claims, stored.embedded.chunks) == (0, 0)
    assert stored.embedding_error == "embedding route timed out"
    claim = await session.get(Claim, claim_id)
    assert claim is not None and claim.embedding is None


async def test_stored_answers_rank_by_any_word_of_the_question(session: AsyncSession) -> None:
    store = answer_store(session)
    await kept_answer(
        store,
        AnswerAsk(question="Why alum?", depth="DETAILED"),
        answer(said(FIGURE_TEXT, ABSTRACT_ID, FIGURE_QUOTE)),
    )
    claim_id = expected_claim_id(FIGURE_KEY)
    found = await store.stored_claims(ZELVAR.slug, "alum quixotically", "HYBRID")
    assert found.views[claim_id].rank > 0
    quiet = await store.stored_claims("Zelvar-Quiet", "alum", "HYBRID")
    assert claim_id not in quiet.views
