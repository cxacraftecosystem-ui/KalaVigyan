from collections.abc import AsyncIterator

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import (
    AuditLog,
    CandidateCheck,
    Claim,
    ClaimSource,
    CuratedClaim,
    Source,
    StructureProposal,
)
from app.research.review_queue import STRUCTURE, QueueApproval, QueueRejection, ReviewFilters
from app.services import review_queue_decisions as decisions
from app.services.review_queue import QueueAdapters, list_review_queue
from app.services.review_queue_errors import DecisionConflict

from ..structure.pages import (
    AFTER_QUOTE,
    HISTORY_CONCEPT,
    NAME_QUOTE,
    PAGE_URL,
    SLUG,
    STAGE_CONCEPT,
    curated_page,
)
from .review_queue_seed import TurnsOf
from .structure_seed import CRAFT, NOW, People, curated_key, proposed, seeded_session, stored_page, with_page

pytestmark = pytest.mark.db

NAME = {"kind": "NATIVE_NAME", "text": "Ajrak", "language": "sd"}
AFTER = {
    "kind": "STAGE_AFTER",
    "stageKey": "P01",
    "text": "Deep red where alum was printed",
    "colours": ["RED"],
}
AFTER_STATEMENT = "After the second wash the cloth turns a deep red where the alum mordant was printed."
ADAPTERS = QueueAdapters(objects=None, turns_of=TurnsOf())


@pytest.fixture
async def seeded() -> AsyncIterator[tuple[AsyncSession, People]]:
    async for opened in seeded_session():
        yield opened


async def approve(session: AsyncSession, people: People, proposal_id: object) -> object:
    ref = decisions.ItemRef(STRUCTURE, proposal_id)
    return await decisions.approve_item(
        session, ref, people.professor, QueueApproval(note="Checked."), now=NOW
    )


async def test_a_researcher_s_native_name_passes_the_checks_and_waits_for_a_reviewer(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    result = await proposed(session, people.researcher, NAME)
    assert (result.outcome, result.status, result.claim_id) == ("STORED", "PENDING", None)
    assert [(check.check, check.passed) for check in result.checks] == [
        ("STATED", True),
        ("QUOTES", True),
        ("SOURCE", True),
    ]
    assert result.page_url == f"https://kalavigyan.example/crafts/{SLUG}"
    kept = await session.scalar(
        select(Source).where(Source.url == PAGE_URL).execution_options(populate_existing=True)
    )
    assert kept is not None and (kept.origin, kept.addedById) == ("CONTRIBUTION", people.researcher.id)
    page = await stored_page(session)
    assert [name.text for name in page.native_names] == ["Ajrakh"]
    listed = await list_review_queue(
        session, people.professor, ReviewFilters(kind=STRUCTURE), adapters=ADAPTERS, now=NOW
    )
    (item,) = listed.items
    assert (item.kind, item.id, item.origin, item.proposer) == (
        "STRUCTURE",
        result.proposal_id,
        "CONTRIBUTION",
        None,
    )
    assert (item.structure.kind, item.structure.stale, item.structure.statement) == (
        "NATIVE_NAME",
        None,
        "Printers in the delta call the cloth ajrak, after their word for blue.",
    )
    assert [quote.text for quote in item.structure.sources[0].quotes] == [NAME_QUOTE]
    assert listed.counts["STRUCTURE"] == 1


async def test_approval_writes_the_name_into_the_page_and_its_dossier_with_a_curated_fact(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    result = await proposed(session, people.researcher, NAME)
    decided = await approve(session, people, result.proposal_id)
    claim_id = curated_key("C004")
    assert decided.status == "APPROVED"
    page = await stored_page(session)
    assert [(name.text, name.language, name.claim_id) for name in page.native_names][-1] == (
        "Ajrak",
        "sd",
        claim_id,
    )
    assert page.claim_order[-1] == claim_id
    claim = await session.get(Claim, claim_id)
    assert (claim.status, claim.evidenceLevel, claim.origin, claim.field) == (
        "APPROVED",
        "PROVISIONAL",
        "CONTRIBUTION",
        "HISTORY",
    )
    assert (claim.subjectId, claim.createdById) == (HISTORY_CONCEPT, people.researcher.id)
    marker = await session.get(CuratedClaim, claim_id)
    assert (marker.key, marker.discipline, marker.craftId) == ("C004", "HISTORY", CRAFT)


async def test_the_approved_fact_cites_its_quote_from_a_source_the_dossier_now_keeps(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    result = await proposed(session, people.researcher, NAME)
    await approve(session, people, result.proposal_id)
    claim_id = curated_key("C004")
    (cited,) = (await session.scalars(select(ClaimSource).where(ClaimSource.claimId == claim_id))).all()
    assert (cited.foundBy, cited.locator, cited.quote, cited.quoteCheck) == (
        "curation",
        "para 1",
        NAME_QUOTE,
        "PASS",
    )
    source = await session.get(Source, cited.sourceId)
    assert {key: source.externalIds[key] for key in ("curation", "language", "access")} == {
        "curation": f"{SLUG}:S01",
        "language": "en",
        "access": "OPEN",
    }
    gates = await session.scalars(select(CandidateCheck.gate).where(CandidateCheck.claimId == claim_id))
    assert sorted(gates.all()) == ["QUOTES", "SOURCE"]
    row = await session.get(StructureProposal, result.proposal_id)
    assert (row.status, row.reviewedById, row.reviewNote, row.claimId) == (
        "APPROVED",
        people.professor.id,
        "Checked.",
        claim_id,
    )
    audited = await session.scalar(
        select(func.count()).where(
            AuditLog.action == "review.structure_approved", AuditLog.targetId == str(row.id)
        )
    )
    assert audited == 1


async def test_a_professor_s_stage_after_is_written_at_once_on_that_stage(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    result = await proposed(session, people.professor, AFTER, quote=AFTER_QUOTE, statement=AFTER_STATEMENT)
    assert (result.outcome, result.status) == ("WRITTEN", "APPROVED")
    page = await stored_page(session)
    first, second = page.stages
    assert (first.after.text, first.after.colours, first.after.claim_id) == (
        AFTER["text"],
        ["RED"],
        result.claim_id,
    )
    assert second.after.text == "Pale"
    claim = await session.get(Claim, result.claim_id)
    assert claim.subjectId == STAGE_CONCEPT


async def test_a_quote_the_page_never_gives_is_refused_and_keeps_nothing(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    result = await proposed(
        session, people.researcher, NAME, text="A page about another cloth entirely, at length."
    )
    assert (result.outcome, result.status) == ("REFUSED", "REFUSED")
    assert result.message.startswith("Not added: the QUOTES check refused it.")
    assert await session.scalar(select(Source).where(Source.url == PAGE_URL)) is None
    listed = await list_review_queue(session, people.professor, ReviewFilters(), adapters=ADAPTERS, now=NOW)
    assert listed.counts["STRUCTURE"] == 0


async def test_a_name_no_quote_gives_is_refused_before_any_page_is_read(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    result = await proposed(session, people.researcher, NAME | {"text": "Ajarak"})
    assert result.outcome == "REFUSED"
    assert [check.check for check in result.checks] == ["STATED"]


async def test_a_proposal_for_a_craft_without_a_curated_page_or_a_missing_stage_is_malformed(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    with pytest.raises(InvalidInput, match="not a stage of this page"):
        await proposed(session, people.researcher, AFTER | {"stageKey": "P07"}, quote=AFTER_QUOTE)
    with pytest.raises(InvalidInput, match="No craft has the slug"):
        await proposed(session, people.researcher, NAME, subject={"kind": "craft", "slug": "No-Such-Craft"})


async def test_a_page_that_moved_on_refuses_approval_and_a_rejection_keeps_the_reason(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    result = await proposed(session, people.researcher, AFTER, quote=AFTER_QUOTE, statement=AFTER_STATEMENT)
    page = curated_page()
    await with_page(session, page.model_copy(update={"stages": page.stages[1:]}))
    with pytest.raises(DecisionConflict, match="P01 is not a stage of this page"):
        await approve(session, people, result.proposal_id)
    rejection = QueueRejection(reason="The page no longer has this stage.")
    ref = decisions.ItemRef(STRUCTURE, result.proposal_id)
    decided = await decisions.reject_item(session, ref, people.professor, rejection, now=NOW)
    row = await session.get(StructureProposal, result.proposal_id)
    assert (decided.status, row.status, row.reviewNote) == ("REJECTED", "REJECTED", rejection.reason)
    with pytest.raises(DecisionConflict, match="rejected already"):
        await approve(session, people, result.proposal_id)
