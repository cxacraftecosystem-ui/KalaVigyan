import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.models import Claim, ClaimSource, Concept, Craft, Source, Term, TermConcept
from app.research.retrieval import KnowledgeQuery
from app.retrieval.hybrid import StoredKnowledgeSearch

from ..craft_fixtures import FixedEmbedder, unit

pytestmark = pytest.mark.db

SLUG = "Nelvar-Print"
NAMES = ("Lead", "Mica", "Sand", "Mati", "Neli", "Atta", "Patna", "Alum", "Begar (alum red)", "Block")
INSIDE_WORDS = (
    "Which chemicals give a thousand shades in the formation of carnelian, "
    "leading dyers from pattachitra to channapatna?"
)


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-entity-names/{name}")


CRAFT, SOURCE, TERM = key("craft"), key("source"), key("term")
CONCEPTS = {name: key(f"concept-{name}") for name in NAMES}
FACTS = {name: key(f"claim-{name}") for name in NAMES}


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
    session.add_all(
        [
            Craft(id=CRAFT, slug=SLUG, name="Nelvar Print"),
            Source(id=SOURCE, kind="BOOK", title="Nelvar notes"),
        ]
    )
    await session.flush()
    session.add_all([Concept(id=CONCEPTS[name], craftId=CRAFT, type="MATERIAL", name=name) for name in NAMES])
    session.add(Term(id=TERM, key="test-nelvar-fitkari", label="Fitkari", localNames=["फिटकरी"]))
    await session.flush()
    session.add(TermConcept(termId=TERM, conceptId=CONCEPTS["Alum"]))
    session.add_all([_fact(name, index) for index, name in enumerate(NAMES)])
    await session.flush()
    session.add_all([ClaimSource(claimId=FACTS[name], sourceId=SOURCE) for name in NAMES])
    await session.flush()


def _fact(name: str, index: int) -> Claim:
    return Claim(
        id=FACTS[name],
        subjectType="CONCEPT",
        subjectId=CONCEPTS[name],
        predicate="explains",
        text=f"Nelvar workshop note {index}.",
        embedding=unit(1.0),
        evidenceLevel="PROVISIONAL",
        origin="IMPORT",
    )


async def named(session: AsyncSession, question: str) -> list[tuple[int, uuid.UUID]]:
    query = KnowledgeQuery(craft_slug=SLUG, text=question, mode="HYBRID", limit=50)
    found = await StoredKnowledgeSearch(session, embed=FixedEmbedder()).search(query)
    return sorted((hit.entity_rank, hit.claim_id) for hit in found.claims if hit.entity_rank is not None)


async def test_a_name_inside_another_word_names_nothing(session: AsyncSession) -> None:
    assert await named(session, INSIDE_WORDS) == []


async def test_whole_names_rank_longest_first_and_a_gloss_still_names_its_concept(
    session: AsyncSession,
) -> None:
    assert await named(session, "Why do the printers put alum in the begar?") == [
        (1, FACTS["Begar (alum red)"]),
        (2, FACTS["Alum"]),
    ]
    assert await named(session, "Which pastes give the alum red?") == [
        (1, FACTS["Begar (alum red)"]),
        (2, FACTS["Alum"]),
    ]


async def test_a_plural_or_a_native_name_still_names_its_concept(session: AsyncSession) -> None:
    assert await named(session, "How are the blocks carved?") == [(1, FACTS["Block"])]
    assert await named(session, "फिटकरी क्यों डालते हैं?") == [(1, FACTS["Alum"])]
