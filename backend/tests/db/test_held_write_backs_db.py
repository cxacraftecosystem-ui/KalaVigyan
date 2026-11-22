from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CandidateCheck, Claim, Concept, Craft, CraftCategory, CraftSubCategory, ReviewEvent
from app.research.composition import ComposedAnswer, ComposedSection
from app.research.crafts import CraftRef
from app.research.evidence_pack import EvidencePack
from app.research.retrieval import HIDDEN_CLAIM_STATUSES, KnowledgeHits
from app.research.sections import DISCIPLINE_TITLES
from app.services.craft_resolver import CraftIndexStore
from app.services.research_write_back import StoredResearch, sentence_claim_ids, store_live_research
from app.services.write_back_crafts import HELD_UNNAMED
from app.sources.adapter import build_document

from ..composer.fixtures import PLAN, packed
from ..craft_fixtures import FixedEmbedder
from ..research.fixtures import evidence_item
from .write_back_seed import ANSWER, CRAFT, ZELVAR, expected_claim_id, key, said, seeded_session

pytestmark = pytest.mark.db

AGED = "The body is aged for two days"
LAKE = "Aluminium ions bind the dye into an insoluble lake"
NOTES = evidence_item(
    id="openalex:held-notes",
    url="https://held.example.org/notes",
    doi=None,
    title="Notes on firing and dyeing",
    quotes=[],
)
NOTES_TEXT = f"{AGED} before it is wedged. {LAKE} on the fibre."
CLAY_CATEGORY, CLAY_FAMILY, QORVEL = key("clay-category"), key("clay-family"), key("qorvel")
QORVEL_REF = CraftRef(slug="Qorvel-Clay", name="Qorvel Clay", path="/crafts/Qorvel-Clay")


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in seeded_session():
        opened.add(
            CraftCategory(id=CLAY_CATEGORY, slug="test-held-clay", name="Test Held Clay", sortOrder=997)
        )
        await opened.flush()
        opened.add(
            CraftSubCategory(
                id=CLAY_FAMILY,
                slug="test-held-clay-family",
                name="Qorvel",
                categoryId=CLAY_CATEGORY,
                sortOrder=1,
            )
        )
        await opened.flush()
        opened.add(Craft(id=QORVEL, slug=QORVEL_REF.slug, name=QORVEL_REF.name, subCategoryId=CLAY_FAMILY))
        await opened.flush()
        yield opened


def notes_pack(craft: CraftRef) -> EvidencePack:
    return EvidencePack(
        plan=PLAN.model_copy(update={"craft": craft}),
        degraded=False,
        stored=KnowledgeHits(craft_slug=craft.slug),
        coverage=({"facetIndex": 0},),
        evidence=(packed(NOTES, "openalex"),),
        documents=(build_document(NOTES, NOTES_TEXT, "FULL_TEXT"),),
    )


def under(discipline: str, text: str, quote: str) -> ComposedAnswer:
    sentence = said(text, NOTES.id, quote)
    return ComposedAnswer(
        sections=[ComposedSection(heading=DISCIPLINE_TITLES[discipline], sentences=[sentence])]
    )


async def written(session: AsyncSession, craft: CraftRef, composed: ComposedAnswer) -> StoredResearch:
    return await store_live_research(
        session,
        notes_pack(craft),
        composed,
        embed=FixedEmbedder(),
        found_by="ANSWER",
        index=CraftIndexStore(),
        answer_id=ANSWER,
    )


async def test_a_sentence_naming_no_craft_is_held_hidden_for_a_reviewer_under_the_craft_researched(
    session: AsyncSession,
) -> None:
    composed = under("PROCESS", f"{AGED}.", AGED)
    stored = await written(session, ZELVAR, composed)
    assert stored.results == ()
    (held,) = stored.held
    assert held.claim_id == expected_claim_id(AGED.casefold(), field="PROCESS") and held.created
    claim = await session.get(Claim, held.claim_id)
    assert claim.status == "DRAFT" and claim.status in HIDDEN_CLAIM_STATUSES
    concept = await session.get(Concept, claim.subjectId)
    assert concept.craftId == CRAFT
    gates = set(
        (await session.scalars(select(CandidateCheck.gate).where(CandidateCheck.claimId == claim.id))).all()
    )
    assert {"QUOTES", "SOURCE", "DUPLICATE"} <= gates
    (event,) = (await session.scalars(select(ReviewEvent).where(ReviewEvent.claimId == claim.id))).all()
    assert (event.systemActor, event.toStatus) == ("live_research_held", "DRAFT")
    assert f"held for a reviewer: it {HELD_UNNAMED}; approving files it under {ZELVAR.slug}" in event.note
    assert sentence_claim_ids(composed, stored) == ((),)


async def test_the_same_general_sentence_is_one_fact_per_family_compared_with_its_own_family(
    session: AsyncSession,
) -> None:
    composed = under("CHEMISTRY", f"{LAKE}.", LAKE)
    textiles = await written(session, ZELVAR, composed)
    clay = await written(session, QORVEL_REF, composed)
    (first,), (second,) = textiles.results, clay.results
    assert first.claim_id != second.claim_id and first.created and second.created
    owners = []
    for result in (first, second):
        claim = await session.get(Claim, result.claim_id)
        concept = await session.get(Concept, claim.subjectId)
        owners.append((concept.craftId, concept.subCategoryId, concept.type, concept.name))
    assert owners == [
        (None, None, "MECHANISM", "Test Write Back"),
        (None, None, "MECHANISM", "Test Held Clay"),
    ]
    again = await written(session, QORVEL_REF, composed)
    assert [(result.claim_id, result.created) for result in again.results] == [(second.claim_id, False)]
