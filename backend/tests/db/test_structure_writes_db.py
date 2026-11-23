from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Claim, ClaimSource, Concept, CraftGiRecord, CuratedClaim, StructureProposal
from app.research.review_queue import STRUCTURE, QueueApproval
from app.services import review_queue_decisions as decisions

from ..structure.pages import BOTANY_QUOTE, GI_QUOTE, HELD_A, HELD_B, HELD_C, NAME_QUOTE, SLUG, source
from .structure_seed import CRAFT, NOW, People, curated_key, proposed, seeded_session, stored_page

pytestmark = pytest.mark.db

GI = {"kind": "GI_RECORD", "applicationNumber": "182", "registeredOn": "2009-03-10"}
GI_STATEMENT = "The craft was registered as a geographical indication on 2009-03-10, application 182."
TERM = {"kind": "GLOSSARY_TERM", "term": "Ajrak", "meaning": "The printed cloth, named for its blue."}
BOTANY = {"kind": "BOTANICAL_NAME", "materialKey": "M01", "botanicalName": "Indigofera tinctoria"}
CONFLICT = {
    "kind": "CONFLICT",
    "about": "Whether the river had dried",
    "claimIds": [str(HELD_A), str(HELD_B)],
}
NAME = {"kind": "NATIVE_NAME", "text": "Ajrak", "language": "sd"}


@pytest.fixture
async def seeded() -> AsyncIterator[tuple[AsyncSession, People]]:
    async for opened in seeded_session():
        yield opened


async def approved(session: AsyncSession, people: People, item: dict[str, Any], **changes: Any) -> Any:
    result = await proposed(session, people.researcher, item, **changes)
    assert result.status == "PENDING", result.checks
    ref = decisions.ItemRef(STRUCTURE, result.proposal_id)
    await decisions.approve_item(session, ref, people.professor, QueueApproval(), now=NOW)
    return await session.get(StructureProposal, result.proposal_id)


async def markers(session: AsyncSession) -> int:
    return int(await session.scalar(select(func.count()).where(CuratedClaim.craftId == CRAFT)) or 0)


async def test_a_conflict_joins_the_page_and_marks_both_facts_without_a_new_fact(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    row = await approved(session, people, CONFLICT, statement=None, sources=[], field=None)
    assert (row.status, row.claimId, row.checks) == ("APPROVED", None, [])
    page = await stored_page(session)
    assert [conflict.claim_ids for conflict in page.conflicts][-1] == [HELD_A, HELD_B]
    differ = await session.execute(
        select(Claim.id, Claim.sourcesDiffer, Claim.differsOn)
        .where(Claim.id.in_([HELD_A, HELD_B, HELD_C]))
        .execution_options(populate_existing=True)
    )
    about = "Whether the river had dried"
    assert {row[0]: tuple(row[1:]) for row in differ.tuples().all()} == {
        HELD_A: (True, about),
        HELD_B: (True, about),
        HELD_C: (False, None),
    }
    assert await markers(session) == 3


async def test_a_gi_record_is_stored_with_the_fact_that_states_it(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    row = await approved(session, people, GI, quote=GI_QUOTE, statement=GI_STATEMENT, field="POLICY")
    record = await session.get(CraftGiRecord, CRAFT)
    assert record is not None
    assert (record.applicationNumber, record.registeredOn, record.claimIds) == (
        "182",
        "2009-03-10",
        [row.claimId],
    )
    assert row.claimId == curated_key("C004")


async def test_a_glossary_term_gets_its_own_concept_under_its_dossier_key(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    row = await approved(session, people, TERM)
    page = await stored_page(session)
    (term,) = page.glossary
    concept = await session.get(Concept, term.concept_id)
    assert (term.key, term.term, term.claim_ids) == ("W01", "Ajrak", [row.claimId])
    assert (concept.type, concept.name, concept.originRef, concept.craftId) == (
        "CONCEPT",
        "Ajrak",
        f"curation:{SLUG}:W01",
        CRAFT,
    )
    claim = await session.get(Claim, row.claimId)
    assert claim.subjectId == concept.id


async def test_a_field_the_page_has_no_concept_for_gets_the_craft_s_concept_for_it(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    row = await approved(session, people, NAME, field="SOCIETY")
    page = await stored_page(session)
    concept_id = page.craft_concepts["SOCIETY"]
    concept = await session.get(Concept, concept_id)
    assert (concept.type, concept.originRef) == ("TRADITION", f"curation:{SLUG}:craft:SOCIETY")
    claim = await session.get(Claim, row.claimId)
    assert claim.subjectId == concept_id


async def test_a_second_proposal_citing_the_same_page_keeps_its_source_key(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    first = await approved(session, people, NAME)
    second = await approved(
        session,
        people,
        BOTANY,
        field="BOTANY",
        statement="The indigo of the delta comes from Indigofera tinctoria.",
        sources=[source(BOTANY_QUOTE)],
    )
    assert (first.claimId, second.claimId) == (curated_key("C004"), curated_key("C005"))
    cited = await session.execute(
        select(ClaimSource.claimId, ClaimSource.sourceId).where(
            ClaimSource.claimId.in_([first.claimId, second.claimId])
        )
    )
    sources = dict(cited.tuples().all())
    assert sources[first.claimId] == sources[second.claimId]
    page = await stored_page(session)
    (material,) = page.materials
    assert (material.botanical_name, material.claim_ids[-1]) == ("Indigofera tinctoria", second.claimId)
    assert NAME_QUOTE in [quote["text"] for quote in first.sources[0]["quotes"]]
