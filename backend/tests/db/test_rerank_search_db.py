import uuid
from collections.abc import AsyncIterator, Sequence

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.models import Claim, ClaimSource, Concept, Craft, CraftCategory, CraftSubCategory, Source
from app.research.reranking import Relevance
from app.research.retrieval import KnowledgeQuery
from app.retrieval.hybrid import StoredKnowledgeSearch

from ..craft_fixtures import FixedEmbedder, unit

pytestmark = pytest.mark.db

SLUG = "Taveri-Print"
QUESTION = "Which mordant fixes the red dye on Taveri cotton?"


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-rerank-search/{name}")


CATEGORY, FAMILY, CRAFT, SOURCE = key("category"), key("family"), key("craft"), key("source")
MORDANT, VAT = key("mordant"), key("vat")
ALUM, ALUM_AGAIN, ALUM_REWORDED = key("alum"), key("alum-again"), key("alum-reworded")
INDIGO, WASH = key("indigo"), key("wash")
TEXTS = {
    ALUM: "Alum fixes the red dye to the Taveri cotton.",
    ALUM_AGAIN: "alum fixes the red dye, to the Taveri cotton",
    ALUM_REWORDED: "The red dye is fixed to Taveri cotton by alum.",
    INDIGO: "Indigo is reduced in a lime vat before Taveri cotton is dyed.",
    WASH: "The printed Taveri cotton is washed in the river after the red dye.",
}
VECTORS = {
    ALUM: unit(1.0, 0.0),
    ALUM_AGAIN: unit(0.0, 1.0),
    ALUM_REWORDED: unit(1.0, 0.1),
    INDIGO: unit(0.0, 0.0, 1.0),
    WASH: unit(0.0, 0.0, 0.0, 1.0),
}
RELEVANCE = {ALUM_AGAIN: 0.95, WASH: 0.80, ALUM: 0.70, INDIGO: 0.40, ALUM_REWORDED: 0.30}


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            session = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
            await _seed(session)
            yield session
            await session.close()
        finally:
            await transaction.rollback()


async def _seed(session: AsyncSession) -> None:
    session.add(CraftCategory(id=CATEGORY, slug="test-taveri", name="Test Taveri", sortOrder=997))
    await session.flush()
    session.add(
        CraftSubCategory(
            id=FAMILY, slug="test-taveri-family", name="Taveri", categoryId=CATEGORY, sortOrder=1
        )
    )
    await session.flush()
    session.add(Craft(id=CRAFT, slug=SLUG, name="Taveri Print", subCategoryId=FAMILY))
    session.add(Source(id=SOURCE, kind="BOOK", title="Taveri printing"))
    await session.flush()
    session.add_all(
        [
            Concept(id=MORDANT, craftId=CRAFT, type="MATERIAL", name="Alum (mordant)"),
            Concept(id=VAT, craftId=CRAFT, type="PROCESS_STAGE", name="Indigo vat"),
        ]
    )
    await session.flush()
    session.add_all([_claim(claim_id) for claim_id in TEXTS])
    await session.flush()
    session.add_all([ClaimSource(claimId=claim_id, sourceId=SOURCE) for claim_id in TEXTS])
    await session.flush()


def _claim(claim_id: uuid.UUID) -> Claim:
    return Claim(
        id=claim_id,
        subjectType="CONCEPT",
        subjectId=VAT if claim_id == INDIGO else MORDANT,
        predicate="explains",
        text=TEXTS[claim_id],
        embedding=VECTORS[claim_id],
        field="PROCESS" if claim_id == INDIGO else "CHEMISTRY",
        evidenceLevel="PROVISIONAL",
        origin="IMPORT",
    )


class ByText:
    def __init__(self) -> None:
        self.asked: list[tuple[str, list[str]]] = []

    async def __call__(self, query: str, documents: Sequence[str]) -> list[Relevance]:
        self.asked.append((query, list(documents)))
        scores = {f"| text: {TEXTS[claim_id]}": score for claim_id, score in RELEVANCE.items()}
        return [
            Relevance(index=index, score=next(s for end, s in scores.items() if document.endswith(end)))
            for index, document in enumerate(documents)
        ]


def asked(limit: int, *, rerank: bool = True) -> KnowledgeQuery:
    return KnowledgeQuery(
        craft_slug=SLUG, text=QUESTION, mode="HYBRID", passages=False, limit=limit, rerank=rerank
    )


async def test_the_reranked_search_keeps_one_slot_per_fact_in_relevance_order(session: AsyncSession) -> None:
    reranker = ByText()
    search = StoredKnowledgeSearch(session, embed=FixedEmbedder(), rerank=reranker)
    found = await search.search(asked(3))
    assert [(hit.claim_id, hit.relevance_score) for hit in found.claims] == [
        (ALUM_AGAIN, 0.95),
        (WASH, 0.80),
        (INDIGO, 0.40),
    ]
    assert found.claims[0].corroborating_ids == (ALUM, ALUM_REWORDED)
    ((query, documents),) = reranker.asked
    assert query == QUESTION and len(documents) == len(TEXTS)
    assert f"title: Taveri Print, Alum (mordant), chemistry | text: {TEXTS[ALUM]}" in documents
    assert f"title: Taveri Print, Indigo vat, process | text: {TEXTS[INDIGO]}" in documents


async def test_a_search_that_asks_for_no_reranking_never_calls_the_reranker(session: AsyncSession) -> None:
    reranker = ByText()
    search = StoredKnowledgeSearch(session, embed=FixedEmbedder(), rerank=reranker)
    found = await search.search(asked(5, rerank=False))
    assert reranker.asked == []
    assert len(found.claims) == len(TEXTS)
    assert all(hit.relevance_score is None and hit.corroborating_ids == () for hit in found.claims)
