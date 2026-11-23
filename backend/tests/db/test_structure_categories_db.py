import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.data.craft_master_loader import ID_NAMESPACE
from app.models import (
    Claim,
    Concept,
    ConceptEdge,
    CuratedCategory,
    CuratedCategoryClaim,
    StructureProposal,
    TermCraft,
)
from app.research.review_queue import STRUCTURE, QueueApproval, ReviewFilters, StructureQueueItem
from app.services import review_queue_decisions as decisions
from app.services.curated_category_index import CuratedCategoryPage
from app.services.curated_index import IndexAlternative
from app.services.review_queue import QueueAdapters, list_review_queue
from app.services.term_glossary import term_id
from app.services.what_if_evidence import _relationships

from ..structure.pages import FORMULA_QUOTE, MATERIAL_CONCEPT, curated_page, indigo, key
from .review_queue_seed import TurnsOf
from .structure_seed import CRAFT, NOW, People, proposed, seeded_session, stored_page, with_page

pytestmark = pytest.mark.db

CATEGORY = key("category")
CATEGORY_SLUG = "structure-test-category"
ALUM_CONCEPT = key("alum-concept")
TERM = {"kind": "GLOSSARY_TERM", "term": "Ajrak", "meaning": "The printed cloth, named for its blue."}
ALTERNATIVE = {"kind": "ALTERNATIVE", "materialKey": "M01", "alternativeKey": "M02"}
ALTERNATIVE_FACT = (
    "Alum binds the dye alizarin to the cotton, a mordant printed in place of the indigo resist."
)
ON_THE_CATEGORY = {"subject": {"kind": "category", "slug": CATEGORY_SLUG}}


@pytest.fixture
async def seeded() -> AsyncIterator[tuple[AsyncSession, People]]:
    async for opened in seeded_session():
        yield opened


def category_key(claim_key: str) -> uuid.UUID:
    return uuid.uuid5(ID_NAMESPACE, f"curation:{CATEGORY_SLUG}:{claim_key}")


def category_page() -> CuratedCategoryPage:
    return CuratedCategoryPage(
        category_slug=CATEGORY_SLUG,
        version=1,
        curated_at=datetime(2026, 11, 1, tzinfo=UTC),
        coverage="THIN",
        searched=[],
        overview={},
        sentence_refs=[],
        conflicts=[],
        open_questions=[],
        glossary=[],
        pictures=[],
    )


async def with_category_page(session: AsyncSession) -> None:
    session.add(
        CuratedCategory(
            categoryId=CATEGORY,
            version=1,
            curatedAt=datetime(2026, 11, 1, tzinfo=UTC),
            coverage="THIN",
            digest="0" * 64,
            page=category_page().model_dump(mode="json", by_alias=True),
        )
    )
    await session.flush()


async def stored_category(session: AsyncSession) -> CuratedCategoryPage:
    row = await session.get(CuratedCategory, CATEGORY, populate_existing=True)
    assert row is not None
    return CuratedCategoryPage.model_validate(row.page)


async def approve(session: AsyncSession, people: People, proposal_id: uuid.UUID) -> StructureProposal:
    ref = decisions.ItemRef(STRUCTURE, proposal_id)
    await decisions.approve_item(session, ref, people.professor, QueueApproval(), now=NOW)
    row = await session.get(StructureProposal, proposal_id, populate_existing=True)
    assert row is not None
    return row


async def test_a_category_s_glossary_term_waits_for_review_under_its_category(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    await with_category_page(session)
    result = await proposed(session, people.researcher, TERM, **ON_THE_CATEGORY)
    assert (result.status, result.subject.kind, result.page_url) == (
        "PENDING",
        "category",
        f"https://kalavigyan.example/categories/{CATEGORY_SLUG}",
    )
    page = await list_review_queue(
        session,
        people.professor,
        ReviewFilters(kind="STRUCTURE"),
        adapters=QueueAdapters(None, TurnsOf()),
        now=NOW,
    )
    (item,) = [each for each in page.items if each.id == result.proposal_id]
    assert isinstance(item, StructureQueueItem)
    assert (item.craft, item.structure.subject.kind, item.structure.page_url) == (
        None,
        "category",
        f"/categories/{CATEGORY_SLUG}",
    )


async def test_an_approved_category_term_is_a_curated_fact_of_the_category_with_no_craft(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    await with_category_page(session)
    result = await proposed(session, people.researcher, TERM, **ON_THE_CATEGORY)
    row = await approve(session, people, result.proposal_id)
    assert (row.status, row.craftId, row.categoryId, row.claimId) == (
        "APPROVED",
        None,
        CATEGORY,
        category_key("C001"),
    )
    (term,) = (await stored_category(session)).glossary
    assert (term.key, term.term, term.claim_ids) == ("W01", "Ajrak", [category_key("C001")])
    marker = await session.get(CuratedCategoryClaim, category_key("C001"))
    assert marker is not None and (marker.categoryId, marker.key, marker.discipline) == (
        CATEGORY,
        "C001",
        "HISTORY",
    )
    concept = await session.get(Concept, term.concept_id)
    assert concept is not None and (concept.craftId, concept.originRef) == (
        None,
        f"curation:{CATEGORY_SLUG}:W01",
    )
    assert term.term_key is not None
    crafted = await session.scalars(
        select(TermCraft.craftId).where(TermCraft.termId == term_id(term.term_key))
    )
    assert crafted.all() == []


async def test_a_category_without_a_curated_page_and_an_unknown_category_are_refused(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    with pytest.raises(InvalidInput, match="has no curated page yet"):
        await proposed(session, people.researcher, TERM, **ON_THE_CATEGORY)
    with pytest.raises(InvalidInput, match="No category has the slug"):
        await proposed(
            session, people.researcher, TERM, subject={"kind": "category", "slug": "no-such-category"}
        )


async def test_an_approved_alternative_joins_the_two_materials_with_a_contrast_edge_on_its_fact(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    session.add(Concept(id=ALUM_CONCEPT, craftId=CRAFT, type="MATERIAL", name="Alum"))
    await session.flush()
    alum = indigo().model_copy(
        update={"key": "M02", "material_id": key("alum"), "concept_id": ALUM_CONCEPT, "name": "Alum"}
    )
    await with_page(session, curated_page(materials=[indigo(), alum]))
    result = await proposed(
        session,
        people.researcher,
        ALTERNATIVE,
        quote=FORMULA_QUOTE,
        statement=ALTERNATIVE_FACT,
        field="CHEMISTRY",
    )
    assert result.status == "PENDING", result.checks
    row = await approve(session, people, result.proposal_id)
    page = await stored_page(session)
    assert page.materials[0].alternatives == [IndexAlternative(key="M02", claim_id=row.claimId)]
    edges = await session.execute(
        select(ConceptEdge.srcId, ConceptEdge.dstId, ConceptEdge.relation, ConceptEdge.claimId).where(
            ConceptEdge.srcId == MATERIAL_CONCEPT
        )
    )
    assert edges.tuples().all() == [(MATERIAL_CONCEPT, ALUM_CONCEPT, "CONTRASTS_WITH", row.claimId)]
    claim = await session.get(Claim, row.claimId)
    assert claim is not None and claim.subjectId == MATERIAL_CONCEPT
    found: list[Any] = await _relationships(session, [MATERIAL_CONCEPT])
    assert [(each.claim_id, each.relation, each.concept_ids) for each in found] == [
        (row.claimId, "CONTRASTS_WITH", frozenset({MATERIAL_CONCEPT, ALUM_CONCEPT}))
    ]
