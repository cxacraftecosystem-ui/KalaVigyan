import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.models import (
    Claim,
    ClaimSource,
    Concept,
    ConceptEdge,
    Craft,
    CraftCategory,
    CraftSubCategory,
    CuratedCategoryClaim,
    Source,
    Term,
    TermConcept,
    TermCraft,
)
from app.research.retrieval import KnowledgeHits, KnowledgeQuery
from app.retrieval.hybrid import StoredKnowledgeSearch, craft_scope
from app.retrieval.shared_links import linked_shared_concepts

from ..craft_fixtures import FixedEmbedder

pytestmark = pytest.mark.db

SLUG = "Tervel-Print"
OTHER_SLUG = "Tervel-Lacquer"


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-linked-shared/{name}")


TEXTILES, WOOD, PRINTS = key("textiles"), key("wood"), key("prints")
CRAFT, OTHER, BOOK = key("craft"), key("other"), key("book")
MORDANT_TERM, LAC_TERM = key("term-mordant"), key("term-lac")
VAT, TERMED, EDGED, UNLINKED, ELSEWHERE, FAMILY = (
    key(f"concept-{name}") for name in ("vat", "termed", "edged", "unlinked", "elsewhere", "family")
)
OWN, TERMED_CLAIM, EDGED_CLAIM, UNLINKED_CLAIM, ELSEWHERE_CLAIM, FAMILY_CLAIM = (
    key(f"claim-{name}") for name in ("own", "termed", "edged", "unlinked", "elsewhere", "family")
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
    session.add_all(
        [
            CraftCategory(
                id=TEXTILES, slug="test-tervel-textiles", name="Test Tervel Textiles", sortOrder=995
            ),
            CraftCategory(id=WOOD, slug="test-tervel-wood", name="Test Tervel Wood", sortOrder=994),
            Source(id=BOOK, kind="BOOK", title="Tervel dyeing"),
        ]
    )
    await session.flush()
    session.add(
        CraftSubCategory(
            id=PRINTS, slug="test-tervel-prints", name="Tervel", categoryId=TEXTILES, sortOrder=1
        )
    )
    await session.flush()
    session.add_all([Craft(id=CRAFT, slug=SLUG, name="Tervel Print", subCategoryId=PRINTS), _other()])
    await session.flush()
    session.add_all([*_concepts(), *_terms()])
    await session.flush()
    session.add_all(_links())
    session.add_all(_claims())
    await session.flush()
    session.add_all([ClaimSource(claimId=claim.id, sourceId=BOOK) for claim in _claims()])
    session.add(
        CuratedCategoryClaim(claimId=FAMILY_CLAIM, categoryId=WOOD, key="C001", discipline="CHEMISTRY")
    )
    await session.flush()


def _other() -> Craft:
    return Craft(id=OTHER, slug=OTHER_SLUG, name="Tervel Lacquer")


def _concepts() -> list[Concept]:
    return [
        Concept(id=VAT, craftId=CRAFT, type="PROCESS_STAGE", name="Tervel mordant vat"),
        Concept(id=TERMED, type="MATERIAL", name="Alum mordant"),
        Concept(id=EDGED, type="MECHANISM", name="Alum lake formation"),
        Concept(id=UNLINKED, type="MATERIAL", name="Alum crystals"),
        Concept(id=ELSEWHERE, type="MATERIAL", name="Alum in lac"),
        Concept(id=FAMILY, type="MATERIAL", name="Alum for wood"),
    ]


def _terms() -> list[Term]:
    return [
        Term(id=MORDANT_TERM, key="test-tervel-mordant", label="Tervel mordant"),
        Term(id=LAC_TERM, key="test-tervel-lac", label="Tervel lac"),
    ]


def _links() -> list[object]:
    return [
        TermCraft(termId=MORDANT_TERM, craftId=CRAFT),
        TermConcept(termId=MORDANT_TERM, conceptId=TERMED),
        TermConcept(termId=MORDANT_TERM, conceptId=FAMILY),
        TermCraft(termId=LAC_TERM, craftId=OTHER),
        TermConcept(termId=LAC_TERM, conceptId=ELSEWHERE),
        ConceptEdge(srcId=VAT, dstId=EDGED, relation="SCIENTIFICALLY_EXPLAINED_BY"),
    ]


def _claim(claim_id: uuid.UUID, subject: uuid.UUID, text: str) -> Claim:
    return Claim(
        id=claim_id,
        subjectType="CONCEPT",
        subjectId=subject,
        predicate="explains",
        text=text,
        evidenceLevel="PROVISIONAL",
        origin="LIVE_RESEARCH",
    )


def _claims() -> list[Claim]:
    return [
        _claim(OWN, VAT, "The Tervel vat holds alum water before the cloth goes in."),
        _claim(TERMED_CLAIM, TERMED, "Alum fixes a red dye to cotton as a mordant."),
        _claim(EDGED_CLAIM, EDGED, "Alum and alizarin form a red lake on the fibre."),
        _claim(UNLINKED_CLAIM, UNLINKED, "Alum crystals dissolve in hot water."),
        _claim(ELSEWHERE_CLAIM, ELSEWHERE, "Alum brightens the lac of a lacquered toy."),
        _claim(FAMILY_CLAIM, FAMILY, "Alum hardens a wood surface before it is painted."),
    ]


async def searched(session: AsyncSession, slug: str) -> set[uuid.UUID]:
    query = KnowledgeQuery(craft_slug=slug, text="What does alum do?", mode="HYBRID", limit=50)
    found: KnowledgeHits = await StoredKnowledgeSearch(session, embed=FixedEmbedder()).search(query)
    return {hit.claim_id for hit in found.claims}


async def test_a_shared_concept_is_linked_to_a_craft_by_its_term_or_an_edge_to_the_craft_s_own_concept(
    session: AsyncSession,
) -> None:
    assert await linked_shared_concepts(session, [CRAFT]) == tuple(sorted([TERMED, EDGED]))
    assert await linked_shared_concepts(session, [OTHER]) == (ELSEWHERE,)
    assert await linked_shared_concepts(session, []) == ()
    assert (await craft_scope(session, SLUG)).linked_ids == tuple(sorted([TERMED, EDGED]))


async def test_a_craft_reads_its_linked_shared_claims_and_never_an_unlinked_or_another_craft_s(
    session: AsyncSession,
) -> None:
    read = await searched(session, SLUG)
    assert {OWN, TERMED_CLAIM, EDGED_CLAIM} <= read
    assert read.isdisjoint({UNLINKED_CLAIM, ELSEWHERE_CLAIM, FAMILY_CLAIM})
    other = await searched(session, OTHER_SLUG)
    assert ELSEWHERE_CLAIM in other
    assert other.isdisjoint({OWN, TERMED_CLAIM, EDGED_CLAIM, UNLINKED_CLAIM, FAMILY_CLAIM})
