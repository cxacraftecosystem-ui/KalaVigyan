import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import AuditLog, Claim, Concept, Craft, ReviewEvent
from app.research.page_revalidation import PageOwners
from app.research.review_queue import QueueApproval, QueueRejection
from app.services import review_queue_decisions as decisions
from app.services.review_queue_refile import filed_owners

from .review_queue_seed import CONCEPT, NOW, PICTURE, RESEARCHED, SLUG, People, seeded_session

pytestmark = pytest.mark.db

OTHER = uuid.uuid5(uuid.NAMESPACE_URL, "test-review-queue-refile/other-craft")
OTHER_SLUG = "Review-Queue-Other-Craft"


@pytest.fixture
async def seeded() -> AsyncIterator[tuple[AsyncSession, People]]:
    async for opened, people in seeded_session():
        opened.add(Craft(id=OTHER, slug=OTHER_SLUG, name="Review Queue Other Craft"))
        await opened.flush()
        yield opened, people


async def test_approving_a_fact_under_another_craft_files_it_there_in_one_decision(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    assert (await filed_owners(session, "FACTS", RESEARCHED, OTHER_SLUG)).crafts == (SLUG,)
    decided = await decisions.approve_item(
        session,
        decisions.ItemRef("FACTS", RESEARCHED),
        people.professor,
        QueueApproval(note="About the other craft.", craft=OTHER_SLUG),
        now=NOW,
    )
    assert decided.status == "APPROVED"
    claim = await session.get(Claim, RESEARCHED)
    concept = await session.get(Concept, claim.subjectId)
    assert (concept.id != CONCEPT, concept.craftId, concept.type, concept.name) == (
        True,
        OTHER,
        "MATERIAL",
        "Indigo",
    )
    notes = (await session.scalars(select(ReviewEvent.note).where(ReviewEvent.claimId == RESEARCHED))).all()
    assert notes == [f"About the other craft.; filed under {OTHER_SLUG}"]
    await session.flush()
    (detail,) = (
        await session.scalars(select(AuditLog.detail).where(AuditLog.targetId == str(RESEARCHED)))
    ).all()
    assert detail["filedUnder"] == OTHER_SLUG


async def test_a_craft_is_named_only_for_a_fact_and_must_exist(seeded: tuple[AsyncSession, People]) -> None:
    session, people = seeded
    with pytest.raises(InvalidInput, match="Only a fact"):
        await decisions.approve_item(
            session,
            decisions.ItemRef("IMAGES", PICTURE),
            people.admin,
            QueueApproval(craft=OTHER_SLUG),
            now=NOW,
        )
    with pytest.raises(InvalidInput, match="No craft has the slug"):
        await decisions.approve_item(
            session,
            decisions.ItemRef("FACTS", RESEARCHED),
            people.professor,
            QueueApproval(craft="No-Such-Craft"),
            now=NOW,
        )
    assert await filed_owners(session, "FACTS", RESEARCHED, None) == PageOwners()


async def test_rejecting_drops_the_fact_where_it_is(seeded: tuple[AsyncSession, People]) -> None:
    session, people = seeded
    decided = await decisions.reject_item(
        session,
        decisions.ItemRef("FACTS", RESEARCHED),
        people.professor,
        QueueRejection(reason="It names no craft of ours."),
        now=NOW,
    )
    claim = await session.get(Claim, RESEARCHED)
    assert (decided.status, claim.subjectId) == ("REJECTED", CONCEPT)
