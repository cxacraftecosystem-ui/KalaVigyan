from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.models import CandidateCheck, Chunk, Claim, ClaimSource
from app.research.composition import ComposedSentence, QuotedSpan
from app.research.evidence import EvidenceItem
from app.research.retrieval import EVERY_CHUNK_ACLS
from app.services.term_research import ResearchedSummary
from app.services.term_store import SqlTermStore
from app.sources.adapter import build_document

from ..craft_fixtures import FixedEmbedder

pytestmark = pytest.mark.db

PAGE = "https://crafts.example.org/ajrakh/neerani-soaking"
TEXT = "Neerani is an emulsion of castor oil, soda ash and camel dung. Cloth is soaked in it at least three times."
SOAKED = "Cloth is soaked in neerani at least three times before printing."
SOAKED_QUOTE = "Cloth is soaked in it at least three times"
BOILED = "Neerani is boiled with turmeric for a day before use."
BOILED_QUOTE = "Neerani is boiled with turmeric for a day"
ITEM = EvidenceItem(
    id=f"searxng:{PAGE}",
    adapter="searxng",
    tier="T4",
    source_type="WEB_PAGE",
    url=PAGE,
    title="Soaking in neerani",
    retrieved_at=datetime(2026, 11, 20, 10, 0, tzinfo=UTC),
    trust="C",
)


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


def store_for(session: AsyncSession, embed: FixedEmbedder | None = None) -> SqlTermStore:
    def sessions() -> AsyncSession:
        return AsyncSession(bind=session.bind, expire_on_commit=False, autoflush=False)

    return SqlTermStore(sessions, acls=EVERY_CHUNK_ACLS, embed=embed)


def said(text: str, quote: str) -> ComposedSentence:
    return ComposedSentence(text=text, evidence_ids=[ITEM.id], spans=[QuotedSpan(ref=ITEM.id, text=quote)])


async def test_a_term_s_research_is_written_back_through_the_gates_unreviewed_with_its_checks(
    session: AsyncSession,
) -> None:
    store = store_for(session)
    term = await store.term("neerani")
    assert term is not None
    found = ResearchedSummary(
        "WEB_SEARCH",
        (build_document(ITEM, TEXT, "FULL_TEXT"),),
        (said(SOAKED, SOAKED_QUOTE), said(BOILED, BOILED_QUOTE)),
    )
    written = await store.write_back(term, found)
    assert len(written) == 1
    claim = await session.get(Claim, written[0])
    assert claim is not None and (claim.text, claim.status, claim.origin) == (
        SOAKED,
        "IN_REVIEW",
        "LIVE_RESEARCH",
    )
    gates = await session.scalars(select(CandidateCheck.gate).where(CandidateCheck.claimId == claim.id))
    assert sorted(gates.all()) == ["DUPLICATE", "QUOTES", "SOURCE"]
    boiled = await session.scalar(select(func.count(Claim.id)).where(Claim.text == BOILED))
    assert boiled == 0


async def test_a_term_s_research_is_searchable_by_vector_as_it_is_written(session: AsyncSession) -> None:
    embed = FixedEmbedder()
    store = store_for(session, embed)
    term = await store.term("neerani")
    assert term is not None
    found = ResearchedSummary(
        "WEB_SEARCH", (build_document(ITEM, TEXT, "FULL_TEXT"),), (said(SOAKED, SOAKED_QUOTE),)
    )
    written = await store.write_back(term, found)
    claim = await session.get(Claim, written[0])
    assert claim is not None and claim.embedding is not None
    assert claim.embeddingModel == await session.scalar(select(func.kv_embedding_model()))
    texts = [words for call in embed.calls for words in call]
    assert any(words.endswith(f"| text: {SOAKED}") for words in texts)
    cited = select(ClaimSource.sourceId).where(ClaimSource.claimId == claim.id)
    kept = (await session.scalars(select(Chunk.embedding).where(Chunk.sourceId.in_(cited)))).all()
    assert kept and all(vector is not None for vector in kept)
