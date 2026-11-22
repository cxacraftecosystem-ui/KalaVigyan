import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.models import Claim, ClaimSource, Concept, Craft, Source, Term, TermConcept
from app.research.blocks import named_in
from app.services import knowledge_view
from app.services.claim_seed import seed_id
from app.services.craft_compare import craft_comparison
from app.services.shared_concepts import craft_shared_science, shared_concept_of
from app.services.shared_term_crafts import refresh_shared_terms

pytestmark = pytest.mark.db

AJRAKH = "Kutch-Ajrakh"
BAGRU = "Bagru-Hand-Block-Print"
ALUM_CRAFTS = [AJRAKH, BAGRU, "Machilipatnam-Kalamkari", "Sanganeri-Hand-Block-Printing"]
ALUM_SENTENCES = [
    "Alum is used as a mordant to fasten the colours.",
    "Post-mordanting with diluted alum (fitkari) in a big copper vessel makes the yellow dye fast.",
    "Alum-based red paste is block-printed where red is needed, and different alum concentrations produce "
    "more shades.",
    "Post-mordanting with diluted alum (fitkari) makes the fugitive turmeric-pomegranate yellow fast.",
]
FOURTH_ALUM = "Alum is ground into the gum paste for the red outline."
REFRESHED_AT = datetime(2026, 11, 22, 3, 0, tzinfo=UTC)
INDIGO_CELLS = [
    "In Dhamadka a small amount of indigo was grown while the river was active.",
    "Indigo blue (nil) is extracted from Indigofera tinctoria; synthetic indigo granules are also used nowadays.",
]


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            session = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
            await refresh_shared_terms(session, now=REFRESHED_AT)
            yield session
            await session.close()
        finally:
            await transaction.rollback()


async def craft(session: AsyncSession, slug: str) -> Craft:
    found = await knowledge_view.resolve_craft(session, slug)
    assert found is not None
    return found


async def test_ajrakh_shares_alum_with_the_crafts_whose_own_claims_name_it(session: AsyncSession) -> None:
    explored = await craft_shared_science(session, await craft(session, AJRAKH))
    keys = [node.term_key for node in explored.nodes]
    assert {"alum", "indigo"} <= set(keys)
    assert [node.label.casefold() for node in explored.nodes] == sorted(
        n.label.casefold() for n in explored.nodes
    )
    alum = explored.nodes[keys.index("alum")]
    assert [entry.craft.slug for entry in alum.crafts] == ALUM_CRAFTS
    assert [entry.sentence.text for entry in alum.crafts] == ALUM_SENTENCES
    assert [entry.sentence.id for entry in alum.crafts] == [f"alum.{n}" for n in range(1, 5)]
    assert seed_id("concept", "ie:ajrakh.material.alum") in alum.crafts[0].concept_ids


async def test_every_edge_rests_on_a_claim_about_that_craft_s_own_concept(session: AsyncSession) -> None:
    explored = await craft_shared_science(session, await craft(session, AJRAKH))
    for node in explored.nodes:
        for entry in node.crafts:
            assert named_in(node.label, entry.sentence)
            claim_id = entry.sentence.citations[0].claim_id
            subject = await session.scalar(select(Claim.subjectId).where(Claim.id == claim_id))
            assert subject in entry.concept_ids


async def test_one_shared_term_lists_its_crafts_by_name_or_from_a_chosen_craft(session: AsyncSession) -> None:
    alum = await shared_concept_of(session, "alum", None)
    assert alum is not None
    assert [entry.craft.slug for entry in alum.node.crafts] == [BAGRU, AJRAKH, *ALUM_CRAFTS[2:]]
    focused = await shared_concept_of(session, "alum", await craft(session, AJRAKH))
    assert focused is not None and [e.craft.slug for e in focused.node.crafts] == ALUM_CRAFTS
    assert await shared_concept_of(session, "no-such-term", None) is None


async def test_ajrakh_and_bagru_are_compared_term_by_term_on_their_own_materials(
    session: AsyncSession,
) -> None:
    crafts = [await craft(session, AJRAKH), await craft(session, BAGRU)]
    compared = await craft_comparison(session, crafts, ["MATERIALS"])
    assert compared is not None
    rows = compared.comparison.rows
    assert [(row.facet, row.term.key if row.term else None) for row in rows[:2]] == [
        ("MATERIALS", "alum"),
        ("MATERIALS", "indigo"),
    ]
    assert [cell.sentence.text for cell in rows[0].cells] == [ALUM_SENTENCES[0], ALUM_SENTENCES[1]]
    assert [cell.sentence.text for cell in rows[1].cells] == INDIGO_CELLS
    claims = [cell.sentence.citations[0].claim_id for row in rows for cell in row.cells if cell is not None]
    assert len(claims) == len(set(claims))


async def test_a_field_neither_craft_has_claims_in_is_not_compared(session: AsyncSession) -> None:
    crafts = [await craft(session, AJRAKH), await craft(session, BAGRU)]
    assert await craft_comparison(session, crafts, ["HEALTH"]) is None


async def test_a_craft_whose_naming_claim_is_its_fourth_about_a_concept_still_shares_the_term(
    session: AsyncSession,
) -> None:
    bagru = await craft(session, BAGRU)
    concepts = list(
        await session.scalars(
            select(Concept.id)
            .join(TermConcept, TermConcept.conceptId == Concept.id)
            .join(Term, Term.id == TermConcept.termId)
            .where(Term.key == "alum", Concept.craftId == bagru.id)
            .order_by(Concept.id)
        )
    )
    await session.execute(update(Claim).where(Claim.subjectId.in_(concepts)).values(status="WITHDRAWN"))
    source = Source(id=uuid.uuid4(), kind="PAPER", title="A paper on Bagru reds")
    session.add(source)
    await session.flush()
    texts = ["Aluminium pots are kept out of the dye house."] * 3 + [FOURTH_ALUM]
    for n, text in enumerate(texts):
        claim_id = uuid.uuid4()
        session.add(
            Claim(
                id=claim_id,
                subjectType="CONCEPT",
                subjectId=concepts[0],
                predicate="states",
                text=text,
                evidenceLevel="PROVISIONAL",
                origin="LIVE_RESEARCH",
                createdAt=REFRESHED_AT + timedelta(minutes=n),
            )
        )
        await session.flush()
        session.add(ClaimSource(claimId=claim_id, sourceId=source.id, quote=text))
    await session.flush()
    await refresh_shared_terms(session, now=REFRESHED_AT)
    alum = await shared_concept_of(session, "alum", None)
    assert alum is not None
    assert [entry.craft.slug for entry in alum.node.crafts] == [BAGRU, AJRAKH, *ALUM_CRAFTS[2:]]
    assert alum.node.crafts[0].sentence.text == FOURTH_ALUM


async def test_a_claim_is_compared_under_the_field_it_is_filed_under_not_its_concept_type(
    session: AsyncSession,
) -> None:
    crafts = [await craft(session, AJRAKH), await craft(session, BAGRU)]
    filed = select(Claim.id).where(Claim.text.in_(ALUM_SENTENCES[:2]))
    await session.execute(update(Claim).where(Claim.id.in_(filed)).values(field="PHYSICS", fields=[]))
    compared = await craft_comparison(session, crafts, ["PHYSICS"])
    assert compared is not None
    (row, *_) = compared.comparison.rows
    assert (row.facet, row.term.key if row.term else None) == ("PHYSICS", "alum")
    assert [cell.sentence.text for cell in row.cells if cell is not None] == ALUM_SENTENCES[:2]
