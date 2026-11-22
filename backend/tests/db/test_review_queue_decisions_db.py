import uuid
from collections.abc import AsyncIterator
from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AuditLog,
    Claim,
    ComponentProposal,
    Concept,
    ConceptEdge,
    ImageContribution,
    MediaAsset,
    ReviewEvent,
)
from app.research.review_queue import FactLevelRaise, FactRetraction, QueueApproval, QueueRejection
from app.services import review_queue_decisions as decisions, testimony_writes
from app.services.review_queue_errors import DecisionConflict, OwnItem, UnknownItem

from .review_queue_seed import (
    ADMIN_OWN,
    AGENT_WAITING,
    HELD,
    LIVE,
    NOW,
    PICTURE,
    PROPOSAL,
    PUBLISHED,
    UNGATED,
    People,
    seeded_session,
)
from .testimony_seed import RecordedObjects, Seeded, seed as seed_testimony

pytestmark = pytest.mark.db

REASON = "The quote does not say this."


@pytest.fixture
async def seeded() -> AsyncIterator[tuple[AsyncSession, People]]:
    async for opened in seeded_session():
        yield opened


def ref(kind: str, item_id: uuid.UUID) -> decisions.ItemRef:
    return decisions.ItemRef(kind, item_id)


async def events(session: AsyncSession, claim_id: uuid.UUID) -> list[tuple[object, ...]]:
    rows = await session.scalars(select(ReviewEvent).where(ReviewEvent.claimId == claim_id))
    return [
        (row.actorKind, row.fromStatus, row.toStatus, row.fromLevel, row.toLevel, row.note) for row in rows
    ]


async def audited(session: AsyncSession, target: uuid.UUID) -> list[str]:
    await session.flush()
    rows = await session.scalars(select(AuditLog.action).where(AuditLog.targetId == str(target)))
    return list(rows)


async def test_approving_a_waiting_fact_publishes_it_and_marks_where_sources_differ(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    decided = await decisions.approve_item(
        session, ref("FACTS", AGENT_WAITING), people.admin, QueueApproval(), now=NOW
    )
    assert (decided.status, decided.level, decided.sources_differ) == ("APPROVED", "PROVISIONAL", True)
    assert (await session.get(Claim, HELD)).sourcesDiffer is True
    assert await events(session, AGENT_WAITING) == [("USER", "DRAFT", "APPROVED", None, None, None)]
    assert await audited(session, AGENT_WAITING) == ["review.fact_approved"]
    with pytest.raises(DecisionConflict):
        await decisions.approve_item(
            session, ref("FACTS", AGENT_WAITING), people.admin, QueueApproval(), now=NOW
        )


async def test_approving_a_live_unreviewed_fact_leaves_its_neighbours_alone(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    decided = await decisions.approve_item(
        session, ref("FACTS", LIVE), people.professor, QueueApproval(), now=NOW
    )
    assert (decided.status, decided.sources_differ) == ("APPROVED", False)
    assert (await session.get(Claim, HELD)).sourcesDiffer is False


async def test_rejecting_a_fact_keeps_the_reason_with_it(seeded: tuple[AsyncSession, People]) -> None:
    session, people = seeded
    decided = await decisions.reject_item(
        session, ref("FACTS", LIVE), people.professor, QueueRejection(reason=REASON), now=NOW
    )
    assert decided.status == "REJECTED"
    assert (await session.get(Claim, LIVE)).status == "REJECTED"
    assert await events(session, LIVE) == [("USER", "IN_REVIEW", "REJECTED", None, None, REASON)]


async def test_raising_a_published_fact_marks_it_reviewed_with_who_and_when(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    decided = await decisions.raise_fact(
        session, PUBLISHED, people.professor, FactLevelRaise(note="Checked."), now=NOW
    )
    claim = await session.get(Claim, PUBLISHED)
    assert (decided.status, decided.level) == ("APPROVED", "REVIEWED")
    assert claim.levelReason == "Reviewed against its quoted sources by a Professor on 2026-11-19"
    assert await events(session, PUBLISHED) == [
        ("USER", "APPROVED", "APPROVED", "PROVISIONAL", "REVIEWED", "Checked.")
    ]
    with pytest.raises(DecisionConflict, match="this one is reviewed"):
        await decisions.raise_fact(session, PUBLISHED, people.admin, FactLevelRaise(), now=NOW)


async def test_raising_a_waiting_fact_publishes_it_reviewed(seeded: tuple[AsyncSession, People]) -> None:
    session, people = seeded
    decided = await decisions.raise_fact(session, AGENT_WAITING, people.admin, FactLevelRaise(), now=NOW)
    assert (decided.status, decided.level, decided.sources_differ) == ("APPROVED", "REVIEWED", True)


async def test_retracting_a_published_fact_hides_it_with_the_reason(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    decided = await decisions.retract_fact(
        session, PUBLISHED, people.professor, FactRetraction(reason=REASON), now=NOW
    )
    assert (decided.status, (await session.get(Claim, PUBLISHED)).status) == ("RETRACTED", "RETRACTED")
    assert await events(session, PUBLISHED) == [("USER", "APPROVED", "RETRACTED", None, None, REASON)]
    with pytest.raises(DecisionConflict):
        await decisions.retract_fact(
            session, AGENT_WAITING, people.professor, FactRetraction(reason=REASON), now=NOW
        )


async def test_a_contributor_may_retract_their_own_published_fact(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    claim = await session.get(Claim, PUBLISHED)
    assert claim is not None
    claim.createdById = people.professor.id
    await session.flush()
    decided = await decisions.retract_fact(
        session, PUBLISHED, people.professor, FactRetraction(reason=REASON), now=NOW
    )
    assert (decided.status, (await session.get(Claim, PUBLISHED)).status) == ("RETRACTED", "RETRACTED")


async def test_a_reviewer_never_decides_their_own_fact_nor_an_ungated_one(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    with pytest.raises(OwnItem):
        await decisions.approve_item(session, ref("FACTS", ADMIN_OWN), people.admin, QueueApproval(), now=NOW)
    with pytest.raises(UnknownItem):
        await decisions.approve_item(session, ref("FACTS", UNGATED), people.admin, QueueApproval(), now=NOW)


async def test_an_approved_proposal_waits_for_a_builder_and_a_decision_is_made_once(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    decided = await decisions.approve_item(
        session, ref("COMPONENTS", PROPOSAL), people.admin, QueueApproval(note="Build it."), now=NOW
    )
    row = await session.get(ComponentProposal, PROPOSAL)
    assert (decided.status, row.status, row.reviewedById, row.reviewedAt, row.reviewNote) == (
        "APPROVED",
        "APPROVED",
        people.admin.id,
        NOW,
        "Build it.",
    )
    assert await audited(session, PROPOSAL) == ["review.component_approved"]
    with pytest.raises(DecisionConflict):
        await decisions.reject_item(
            session, ref("COMPONENTS", PROPOSAL), people.admin, QueueRejection(reason=REASON), now=NOW
        )


async def test_a_rejected_proposal_keeps_its_reason(seeded: tuple[AsyncSession, People]) -> None:
    session, people = seeded
    await decisions.reject_item(
        session, ref("COMPONENTS", PROPOSAL), people.admin, QueueRejection(reason=REASON), now=NOW
    )
    row = await session.get(ComponentProposal, PROPOSAL)
    assert (row.status, row.reviewNote) == ("REJECTED", REASON)


async def test_a_picture_is_decided_through_its_own_service(seeded: tuple[AsyncSession, People]) -> None:
    session, people = seeded
    decided = await decisions.approve_item(
        session, ref("IMAGES", PICTURE), people.admin, QueueApproval(), now=NOW
    )
    row = await session.get(ImageContribution, PICTURE)
    asset = await session.get(MediaAsset, row.assetId)
    assert (decided.status, row.reviewedById, asset.visibility, asset.approvedById) == (
        "APPROVED",
        people.admin.id,
        "CRAFT_SHARED",
        people.admin.id,
    )
    assert await audited(session, PICTURE) == ["review.image_approved"]
    with pytest.raises(DecisionConflict):
        await decisions.reject_item(
            session, ref("IMAGES", PICTURE), people.admin, QueueRejection(reason=REASON), now=NOW
        )


async def test_a_rejected_picture_stays_private_with_its_reason(seeded: tuple[AsyncSession, People]) -> None:
    session, people = seeded
    await decisions.reject_item(
        session, ref("IMAGES", PICTURE), people.admin, QueueRejection(reason=REASON), now=NOW
    )
    row = await session.get(ImageContribution, PICTURE)
    assert (row.status, row.reviewNote, (await session.get(MediaAsset, row.assetId)).visibility) == (
        "REJECTED",
        REASON,
        "PRIVATE",
    )


async def approved_testimony(session: AsyncSession, seeded: Seeded) -> uuid.UUID:
    approval = QueueApproval(version=seeded.contribution.version, english_checked=True)
    decided = await decisions.approve_item(
        session, ref("TESTIMONY", seeded.contribution.id), seeded.reviewer, approval, now=NOW
    )
    assert decided.status == "APPROVED"
    claim = await session.get(Claim, seeded.contribution.claimId)
    return claim.subjectId


async def test_testimony_is_decided_through_its_own_service_with_its_reason(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    testimony = await seed_testimony(session)
    rejection = QueueRejection(reason="Misheard.", version=1, testimony_reason="MISHEARD")
    with pytest.raises(UnknownItem):
        await decisions.reject_item(session, ref("TESTIMONY", uuid.uuid4()), people.admin, rejection, now=NOW)
    decided = await decisions.reject_item(
        session, ref("TESTIMONY", testimony.contribution.id), people.admin, rejection, now=NOW
    )
    assert (decided.status, testimony.contribution.rejectReason, testimony.contribution.reviewNote) == (
        "REJECTED",
        "MISHEARD",
        "Misheard.",
    )


async def test_testimony_rejected_by_its_reason_alone_keeps_no_note(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    testimony = await seed_testimony(session)
    rejection = QueueRejection(version=1, testimony_reason="UNCLEAR")
    decided = await decisions.reject_item(
        session, ref("TESTIMONY", testimony.contribution.id), people.admin, rejection, now=NOW
    )
    assert (decided.status, testimony.contribution.rejectReason, testimony.contribution.reviewNote) == (
        "REJECTED",
        "UNCLEAR",
        None,
    )


async def test_erased_testimony_takes_the_concept_it_alone_rested_on(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, _people = seeded
    testimony = await seed_testimony(session)
    concept_id = await approved_testimony(session, testimony)
    await session.flush()
    later = NOW + timedelta(hours=1)
    await testimony_writes.withdraw(
        session, RecordedObjects(), testimony.artisan, testimony.contribution.id, now=later
    )
    await session.flush()
    assert await session.get(Concept, concept_id, populate_existing=True) is None


async def test_erased_testimony_leaves_a_concept_that_something_else_still_links(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, _people = seeded
    testimony = await seed_testimony(session)
    concept_id = await approved_testimony(session, testimony)
    other = Concept(id=uuid.uuid4(), craftId=testimony.craft.id, type="PROCESS_STAGE", name="Drying")
    session.add(other)
    await session.flush()
    session.add(ConceptEdge(srcId=concept_id, dstId=other.id, relation="PRECEDES"))
    await session.flush()
    later = NOW + timedelta(hours=1)
    await testimony_writes.withdraw(
        session, RecordedObjects(), testimony.artisan, testimony.contribution.id, now=later
    )
    await session.flush()
    assert await session.get(Concept, concept_id, populate_existing=True) is not None
