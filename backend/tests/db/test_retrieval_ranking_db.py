import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.models import (
    Claim,
    ClaimSource,
    Concept,
    Craft,
    CraftCategory,
    CraftSubCategory,
    Source,
    Term,
    TermConcept,
)
from app.research.retrieval import KnowledgeHits, KnowledgeQuery
from app.retrieval.hybrid import StoredKnowledgeSearch

from ..craft_fixtures import FixedEmbedder, unit

pytestmark = pytest.mark.db

SLUG = "Varnel-Print"


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-retrieval-ranking/{name}")


CATEGORY, FAMILY, CRAFT, SOURCE = key("category"), key("family"), key("craft"), key("source")
FOUNDER, SYAHI, BEGAR, EMULSION = key("founder"), key("syahi"), key("begar"), key("emulsion")
SETTLED = key("claim-settled")
TALKS = [key(f"claim-talk-{n}") for n in range(4)]
BLACK, RED, SOAK = key("claim-black"), key("claim-red"), key("claim-soak")
TALK = (
    "Ismail Khatri of Varnel told visitors that Ismail Khatri's Varnel workshop, "
    "the oldest Varnel workshop, still uses Varnel river water ({n})."
)


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
    session.add(CraftCategory(id=CATEGORY, slug="test-varnel", name="Test Varnel", sortOrder=998))
    await session.flush()
    session.add(
        CraftSubCategory(
            id=FAMILY, slug="test-varnel-family", name="Varnel", categoryId=CATEGORY, sortOrder=1
        )
    )
    await session.flush()
    session.add(Craft(id=CRAFT, slug=SLUG, name="Varnel Print", subCategoryId=FAMILY))
    session.add(Source(id=SOURCE, kind="BOOK", title="Varnel printing"))
    await session.flush()
    session.add_all(_concepts())
    await session.flush()
    session.add(Term(id=key("term"), key="test-varnel-neerani", label="Neerani", aliases=["nirani"]))
    await session.flush()
    session.add(TermConcept(termId=key("term"), conceptId=EMULSION))
    session.add_all(_claims())
    await session.flush()
    session.add_all([ClaimSource(claimId=claim.id, sourceId=SOURCE) for claim in _claims()])
    await session.flush()


def _concepts() -> list[Concept]:
    return [
        Concept(id=FOUNDER, craftId=CRAFT, type="HISTORICAL_CONTEXT", name="Founding family"),
        Concept(id=SYAHI, craftId=CRAFT, type="MATERIAL", name="Syahi (fermented iron black)"),
        Concept(id=BEGAR, craftId=CRAFT, type="MATERIAL", name="Begar (alum red)"),
        Concept(id=EMULSION, craftId=CRAFT, type="MATERIAL", name="Castor oil emulsion"),
    ]


def _claim(claim_id: uuid.UUID, subject: uuid.UUID, text: str) -> Claim:
    return Claim(
        id=claim_id,
        subjectType="CONCEPT",
        subjectId=subject,
        predicate="explains",
        text=text,
        embedding=unit(0.0, 1.0),
        evidenceLevel="PROVISIONAL",
        origin="IMPORT",
    )


def _claims() -> list[Claim]:
    return [
        _claim(SETTLED, FOUNDER, "Ismail Khatri settled in Varnel in 1962."),
        *(_claim(talk, FOUNDER, TALK.format(n=n)) for n, talk in enumerate(TALKS)),
        _claim(BLACK, SYAHI, "The black paste is fermented from scrap iron and jaggery for a fortnight."),
        _claim(RED, BEGAR, "The red paste is alum thickened with gum."),
        _claim(SOAK, EMULSION, "The cloth is soaked overnight in castor oil, soda ash and camel dung."),
    ]


async def searched(session: AsyncSession, question: str) -> KnowledgeHits:
    search = StoredKnowledgeSearch(session, embed=FixedEmbedder())
    return await search.search(KnowledgeQuery(craft_slug=SLUG, text=question, mode="HYBRID"))


async def test_the_claim_matching_the_rare_word_outranks_claims_repeating_the_common_names(
    session: AsyncSession,
) -> None:
    found = await searched(session, "When did Ismail Khatri settle in Varnel?")
    lexical = sorted((hit.lexical_rank, hit.claim_id) for hit in found.claims if hit.lexical_rank is not None)
    assert lexical[0] == (1, SETTLED)
    assert {claim for _, claim in lexical[1:]} == set(TALKS)


async def test_a_concept_named_natively_before_its_gloss_ranks_its_claims(session: AsyncSession) -> None:
    found = await searched(session, "What is syahi made from?")
    named = [(hit.entity_rank, hit.claim_id) for hit in found.claims if hit.entity_rank is not None]
    assert named == [(1, BLACK)]


async def test_a_concept_named_by_its_gloss_ranks_its_claims(session: AsyncSession) -> None:
    found = await searched(session, "Which pastes give the alum red?")
    named = [(hit.entity_rank, hit.claim_id) for hit in found.claims if hit.entity_rank is not None]
    assert named == [(1, RED)]


async def test_a_concept_named_by_a_glossary_term_or_its_alias_ranks_its_claims(
    session: AsyncSession,
) -> None:
    for question in ("What goes into neerani?", "How long does the cloth stay in nirani?"):
        found = await searched(session, question)
        named = [(hit.entity_rank, hit.claim_id) for hit in found.claims if hit.entity_rank is not None]
        assert named == [(1, SOAK)], question
