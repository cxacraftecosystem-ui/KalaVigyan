import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.curation.checks import default_context
from app.curation.files import CURATION_DIR
from app.models import CandidateCheck, Claim, Craft, User
from app.research.review_queue import FactLevelRaise, FactRetraction, QueueApproval
from app.services import review_queue_decisions as decisions
from app.services.candidate_writes import mark_sources_differ
from app.services.curation_import import import_path
from app.services.curation_keys import curated_id
from app.services.source_corrections import clear_sources_differ

from ..curation.import_support import AJRAKH
from .review_queue_seed import AGENT_WAITING, HELD, NOW, People, seeded_session
from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

OTHER = uuid.uuid5(uuid.NAMESPACE_URL, "test-sources-differ/other-craft")
OTHER_SLUG = "Sources-Differ-Other-Craft"
CONTRIBUTED = uuid.uuid5(uuid.NAMESPACE_URL, "test-sources-differ/contributed")
UNCONFLICTED = "C002"
DIFFERING_TEXT = "Ajrakh is printed on one side of the cloth only."
WRONG = "The quote was misread."
SETTLED = "Both sources describe the same dye bath."
SOAKING, SOAKING_PARTNER = "C064", "C065"


@pytest.fixture
async def seeded() -> AsyncIterator[tuple[AsyncSession, People]]:
    async for opened, people in seeded_session():
        opened.add(Craft(id=OTHER, slug=OTHER_SLUG, name="Sources Differ Other Craft"))
        await opened.flush()
        yield opened, people


async def flags(session: AsyncSession, *claim_ids: uuid.UUID) -> dict[uuid.UUID, bool]:
    rows = await session.execute(
        select(Claim.id, Claim.sourcesDiffer)
        .where(Claim.id.in_(claim_ids))
        .execution_options(populate_existing=True)
    )
    return dict(rows.tuples().all())


def fact(claim_id: uuid.UUID) -> decisions.ItemRef:
    return decisions.ItemRef("FACTS", claim_id)


async def test_retracting_the_only_differing_fact_clears_its_rival_s_flag(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    await decisions.approve_item(session, fact(AGENT_WAITING), people.admin, QueueApproval(), now=NOW)
    assert await flags(session, AGENT_WAITING, HELD) == {AGENT_WAITING: True, HELD: True}
    decided = await decisions.retract_fact(
        session, AGENT_WAITING, people.professor, FactRetraction(reason=WRONG), now=NOW
    )
    assert (decided.status, decided.sources_differ) == ("RETRACTED", False)
    assert await flags(session, AGENT_WAITING, HELD) == {AGENT_WAITING: False, HELD: False}


async def test_approving_a_fact_under_another_craft_flags_neither_craft_s_facts(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    decided = await decisions.approve_item(
        session, fact(AGENT_WAITING), people.admin, QueueApproval(craft=OTHER_SLUG), now=NOW
    )
    assert (decided.status, decided.sources_differ) == ("APPROVED", False)
    assert await flags(session, AGENT_WAITING, HELD) == {AGENT_WAITING: False, HELD: False}


async def test_refiling_an_approved_fact_under_another_craft_clears_both_flags(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    await decisions.approve_item(session, fact(AGENT_WAITING), people.admin, QueueApproval(), now=NOW)
    assert await flags(session, AGENT_WAITING, HELD) == {AGENT_WAITING: True, HELD: True}
    await decisions.approve_item(
        session, fact(AGENT_WAITING), people.professor, QueueApproval(craft=OTHER_SLUG), now=NOW
    )
    assert await flags(session, AGENT_WAITING, HELD) == {AGENT_WAITING: False, HELD: False}


async def test_a_mark_a_person_cleared_is_not_raised_again_by_a_later_decision(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    await decisions.approve_item(session, fact(AGENT_WAITING), people.admin, QueueApproval(), now=NOW)
    await clear_sources_differ(session, HELD, actor=people.admin, reason=SETTLED)
    await session.flush()
    decided = await decisions.raise_fact(session, AGENT_WAITING, people.professor, FactLevelRaise(), now=NOW)
    assert (decided.level, decided.sources_differ) == ("REVIEWED", False)
    assert await flags(session, AGENT_WAITING, HELD) == {AGENT_WAITING: False, HELD: False}


@pytest.fixture
async def imported() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        outcome = await import_path(opened, CURATION_DIR / f"{AJRAKH}.json", default_context())
        assert outcome.status == "IMPORTED", outcome.problems
        yield opened


async def test_a_later_import_keeps_the_flag_a_live_differing_fact_set_on_a_curated_fact(
    imported: AsyncSession,
) -> None:
    session = imported
    curated = curated_id(AJRAKH, UNCONFLICTED)
    held = await session.get(Claim, curated)
    assert held is not None and held.sourcesDiffer is False
    session.add(
        Claim(
            id=CONTRIBUTED,
            subjectType="CONCEPT",
            subjectId=held.subjectId,
            predicate="states",
            text=DIFFERING_TEXT,
            evidenceLevel="PROVISIONAL",
            origin="CONTRIBUTION",
            status="IN_REVIEW",
            field=held.field,
        )
    )
    await session.flush()
    session.add(
        CandidateCheck(
            claimId=CONTRIBUTED,
            gate="DUPLICATE",
            passed=True,
            reasons=["it differs on how many sides are printed"],
            relatedClaimIds=[curated],
            checkedAt=NOW,
        )
    )
    await session.flush()
    assert await mark_sources_differ(session, CONTRIBUTED) == [curated]
    again = await import_path(session, CURATION_DIR / f"{AJRAKH}.json", default_context())
    assert (again.status, again.changed.get("claims")) == ("IMPORTED", None)
    assert await flags(session, curated, CONTRIBUTED) == {curated: True, CONTRIBUTED: True}


async def test_a_mark_a_person_cleared_stays_cleared_when_the_dossier_is_imported_again(
    imported: AsyncSession,
) -> None:
    session = imported
    cleared, partner = curated_id(AJRAKH, SOAKING), curated_id(AJRAKH, SOAKING_PARTNER)
    assert await flags(session, cleared, partner) == {cleared: True, partner: True}
    token = uuid.uuid4()
    admin = User(id=token, name="Admin Clearer", email=f"{token.hex[:12]}@example.org", role="ADMIN")
    session.add(admin)
    await session.flush()
    await clear_sources_differ(session, cleared, actor=admin, reason=SETTLED)
    await session.flush()
    again = await import_path(session, CURATION_DIR / f"{AJRAKH}.json", default_context())
    assert (again.status, again.changed.get("claims")) == ("IMPORTED", None)
    assert await flags(session, cleared, partner) == {cleared: False, partner: True}
