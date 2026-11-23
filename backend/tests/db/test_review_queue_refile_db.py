import uuid
from collections.abc import AsyncIterator

import pytest
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import AuditLog, Claim, Concept, Craft, CraftCategory, ReviewEvent
from app.research.page_revalidation import PageOwners
from app.research.review_queue import ONE_HOME, FactRetraction, QueueApproval, QueueRejection
from app.services import review_queue_decisions as decisions
from app.services.review_queue_refile import FAMILY_FIELDS_ONLY, filed_owners

from .review_queue_seed import CONCEPT, NOW, PICTURE, RESEARCHED, SLUG, People, seeded_session

pytestmark = pytest.mark.db

OTHER = uuid.uuid5(uuid.NAMESPACE_URL, "test-review-queue-refile/other-craft")
OTHER_SLUG = "Review-Queue-Other-Craft"
FAMILY = uuid.uuid5(uuid.NAMESPACE_URL, "test-review-queue-refile/family")
FAMILY_SLUG, FAMILY_NAME = "Review-Queue-Test-Family", "Review Queue Test Family"
OLD_WRITE_BACK = uuid.uuid5(uuid.NAMESPACE_URL, "test-review-queue-refile/old-write-back")


@pytest.fixture
async def seeded() -> AsyncIterator[tuple[AsyncSession, People]]:
    async for opened, people in seeded_session():
        opened.add(Craft(id=OTHER, slug=OTHER_SLUG, name="Review Queue Other Craft"))
        opened.add(CraftCategory(id=FAMILY, slug=FAMILY_SLUG, name=FAMILY_NAME, sortOrder=996))
        opened.add(
            Claim(
                id=OLD_WRITE_BACK,
                text="Indigo vats are fermented for days.",
                subjectType="CONCEPT",
                subjectId=CONCEPT,
                predicate="states",
                evidenceLevel="PROVISIONAL",
                origin="LIVE_RESEARCH",
                field="PROCESS",
                status="APPROVED",
                createdByKind="SYSTEM",
            )
        )
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


async def test_approving_a_fact_under_a_family_files_it_under_that_family_s_science(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    assert (await filed_owners(session, "FACTS", RESEARCHED, FAMILY_SLUG)).crafts == (SLUG,)
    decided = await decisions.approve_item(
        session,
        decisions.ItemRef("FACTS", RESEARCHED),
        people.professor,
        QueueApproval(family=FAMILY_SLUG.lower()),
        now=NOW,
    )
    assert decided.status == "APPROVED"
    claim = await session.get(Claim, RESEARCHED)
    concept = await session.get(Concept, claim.subjectId)
    assert (concept.craftId, concept.subCategoryId, concept.type, concept.name) == (
        None,
        None,
        "MECHANISM",
        FAMILY_NAME,
    )
    notes = (await session.scalars(select(ReviewEvent.note).where(ReviewEvent.claimId == RESEARCHED))).all()
    assert notes == [f"filed under the family science of {FAMILY_SLUG.lower()}"]
    await session.flush()
    (detail,) = (
        await session.scalars(select(AuditLog.detail).where(AuditLog.targetId == str(RESEARCHED)))
    ).all()
    assert detail["filedUnderFamily"] == FAMILY_SLUG.lower()


async def test_a_family_takes_only_material_science_and_never_beside_a_craft(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    with pytest.raises(ValidationError, match=ONE_HOME):
        QueueApproval(craft=OTHER_SLUG, family=FAMILY_SLUG)
    with pytest.raises(InvalidInput, match=FAMILY_FIELDS_ONLY):
        await decisions.approve_item(
            session,
            decisions.ItemRef("FACTS", OLD_WRITE_BACK),
            people.professor,
            QueueApproval(family=FAMILY_SLUG),
            now=NOW,
        )
    with pytest.raises(InvalidInput, match="No category has the slug"):
        await decisions.approve_item(
            session,
            decisions.ItemRef("FACTS", RESEARCHED),
            people.professor,
            QueueApproval(family="No-Such-Family"),
            now=NOW,
        )


async def test_an_older_write_back_without_gate_checks_is_refiled_and_retracted_in_the_queue(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    ref = decisions.ItemRef("FACTS", OLD_WRITE_BACK)
    moved = await decisions.approve_item(
        session, ref, people.professor, QueueApproval(craft=OTHER_SLUG), now=NOW
    )
    claim = await session.get(Claim, OLD_WRITE_BACK)
    concept = await session.get(Concept, claim.subjectId)
    assert (moved.status, concept.craftId, concept.name) == ("APPROVED", OTHER, "Indigo")
    retracted = await decisions.retract_fact(
        session, OLD_WRITE_BACK, people.professor, FactRetraction(reason="Not about this craft."), now=NOW
    )
    assert retracted.status == "RETRACTED"
