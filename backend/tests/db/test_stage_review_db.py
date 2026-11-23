import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import Claim, ClaimSource, Concept, Craft, Process, ProcessStage, Source, StageReview, User
from app.research.review_queue import QueueApproval, QueueRejection, ReviewFilters, ReviewQueuePage
from app.services import review_queue_decisions as decisions
from app.services.review_queue import QueueAdapters, list_review_queue
from app.services.review_queue_errors import DecisionConflict

from .review_queue_seed import TurnsOf
from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 23, 9, tzinfo=UTC)
SLUG = "Stage-Review-Test-Craft"
ADAPTERS = QueueAdapters(objects=None, turns_of=TurnsOf())


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-stage-review/{name}")


CRAFT, PROFESSOR, SOURCE, TOLD = key("craft"), key("professor"), key("source"), key("told")
SEEDED, CURATED, FOUND, UNTOLD, NAMED = (
    key("seeded"),
    key("curated"),
    key("found"),
    key("untold"),
    key("named"),
)
SOAKING, PRINTING, WASHING, CURATED_STEP = (
    key("soaking"),
    key("printing"),
    key("washing"),
    key("curated-step"),
)


@pytest.fixture
async def seeded() -> AsyncIterator[tuple[AsyncSession, User]]:
    async for session in rolled_back_session():
        professor = User(id=PROFESSOR, name="Professor Placer", email="placer@example.org", role="PROFESSOR")
        session.add_all([professor, Craft(id=CRAFT, slug=SLUG, name="Stage Review Test Craft")])
        session.add(Source(id=SOURCE, kind="PAPER", title="Drying printed cloth", reliability="B"))
        session.add(Process(id=SEEDED, craftId=CRAFT, name="Process", variant="seed_claims"))
        session.add(Process(id=CURATED, craftId=CRAFT, name="Curated process", variant="curation"))
        await session.flush()
        session.add_all(_stages())
        session.add_all(_concepts())
        await session.flush()
        session.add(_told())
        await session.flush()
        session.add(ClaimSource(claimId=TOLD, sourceId=SOURCE, quote="dried in the sun", quoteCheck="PASS"))
        await session.flush()
        yield session, professor


def _stages() -> list[ProcessStage]:
    return [
        ProcessStage(id=SOAKING, processId=SEEDED, ordinal=1, name="Soaking"),
        ProcessStage(id=PRINTING, processId=SEEDED, ordinal=2, name="Printing"),
        ProcessStage(id=WASHING, processId=SEEDED, ordinal=3, name="Washing"),
        ProcessStage(id=CURATED_STEP, processId=CURATED, ordinal=1, name="Mordanting"),
    ]


def _concepts() -> list[Concept]:
    live = {"craftId": CRAFT, "type": "PROCESS_STAGE", "originRef": "live_research"}
    return [
        Concept(id=FOUND, name="Drying in the sun", createdAt=NOW - timedelta(minutes=5), **live),
        Concept(id=UNTOLD, name="Folding", createdAt=NOW - timedelta(minutes=4), **live),
        Concept(id=NAMED, craftId=CRAFT, type="PROCESS_STAGE", name="Steaming", createdAt=NOW),
    ]


def _told() -> Claim:
    return Claim(
        id=TOLD,
        subjectType="CONCEPT",
        subjectId=FOUND,
        predicate="states",
        text="The printed cloth is dried in the sun.",
        evidenceLevel="PROVISIONAL",
        origin="LIVE_RESEARCH",
        status="APPROVED",
        createdByKind="SYSTEM",
    )


async def listed(session: AsyncSession, viewer: User) -> ReviewQueuePage:
    filters = ReviewFilters(craft_slug=SLUG, kind="STAGES")
    return await list_review_queue(session, viewer, filters, adapters=ADAPTERS, now=NOW)


async def ordinals(session: AsyncSession) -> list[tuple[str, int]]:
    rows = await session.execute(
        select(ProcessStage.name, ProcessStage.ordinal)
        .where(ProcessStage.processId == SEEDED)
        .order_by(ProcessStage.ordinal)
    )
    return [(name, ordinal) for name, ordinal in rows.tuples().all()]


async def test_a_stage_answers_found_waits_with_its_facts_and_the_processes_it_can_join(
    seeded: tuple[AsyncSession, User],
) -> None:
    session, professor = seeded
    page = await listed(session, professor)
    assert (page.counts["STAGES"], [item.id for item in page.items]) == (1, [FOUND])
    (item,) = page.items
    assert item.kind == "STAGES" and item.origin == "RESEARCH" and item.proposer is None
    placing = item.stage
    assert placing.name == "Drying in the sun"
    assert [(process.id, [step.name for step in process.stages]) for process in placing.processes] == [
        (SEEDED, ["Soaking", "Printing", "Washing"])
    ]
    (fact,) = placing.facts
    assert (fact.id, fact.text) == (TOLD, "The printed cloth is dried in the sun.")
    assert [(source.title, [quote.text for quote in source.quotes]) for source in fact.sources] == [
        ("Drying printed cloth", ["dried in the sun"])
    ]


async def test_placing_a_stage_after_another_moves_the_later_stages_down_and_keeps_the_note(
    seeded: tuple[AsyncSession, User],
) -> None:
    session, professor = seeded
    approval = QueueApproval(process_id=SEEDED, after_stage_id=PRINTING, note="Dried before washing.")
    decided = await decisions.approve_item(
        session, decisions.ItemRef("STAGES", FOUND), professor, approval, now=NOW
    )
    assert (decided.kind, decided.id, decided.status) == ("STAGES", FOUND, "PLACED")
    assert await ordinals(session) == [
        ("Soaking", 1),
        ("Printing", 2),
        ("Drying in the sun", 3),
        ("Washing", 4),
    ]
    review = await session.get(StageReview, FOUND)
    assert review is not None and (review.status, review.note, review.reviewerId) == (
        "PLACED",
        "Dried before washing.",
        PROFESSOR,
    )
    placed = await session.get(ProcessStage, review.processStageId)
    assert placed is not None and (placed.conceptId, placed.processId) == (FOUND, SEEDED)
    assert (await listed(session, professor)).counts["STAGES"] == 0


async def test_placing_first_moves_every_stage_down(seeded: tuple[AsyncSession, User]) -> None:
    session, professor = seeded
    approval = QueueApproval(process_id=SEEDED)
    await decisions.approve_item(session, decisions.ItemRef("STAGES", FOUND), professor, approval, now=NOW)
    assert await ordinals(session) == [
        ("Drying in the sun", 1),
        ("Soaking", 2),
        ("Printing", 3),
        ("Washing", 4),
    ]


@pytest.mark.parametrize(
    ("approval", "refusal"),
    [
        (QueueApproval(), InvalidInput),
        (QueueApproval(process_id=CURATED, after_stage_id=CURATED_STEP), DecisionConflict),
        (QueueApproval(process_id=SEEDED, after_stage_id=CURATED_STEP), InvalidInput),
    ],
)
async def test_a_stage_is_placed_only_into_a_process_that_takes_it(
    seeded: tuple[AsyncSession, User], approval: QueueApproval, refusal: type[Exception]
) -> None:
    session, professor = seeded
    with pytest.raises(refusal):
        await decisions.approve_item(
            session, decisions.ItemRef("STAGES", FOUND), professor, approval, now=NOW
        )
    assert await ordinals(session) == [("Soaking", 1), ("Printing", 2), ("Washing", 3)]


async def test_a_rejected_stage_keeps_its_reason_and_cannot_be_decided_again(
    seeded: tuple[AsyncSession, User],
) -> None:
    session, professor = seeded
    ref = decisions.ItemRef("STAGES", FOUND)
    rejection = QueueRejection(reason="Drying is not a stage of this craft.")
    decided = await decisions.reject_item(session, ref, professor, rejection, now=NOW)
    assert decided.status == "REJECTED"
    review = await session.get(StageReview, FOUND)
    assert review is not None and (review.status, review.note, review.processStageId) == (
        "REJECTED",
        "Drying is not a stage of this craft.",
        None,
    )
    assert await ordinals(session) == [("Soaking", 1), ("Printing", 2), ("Washing", 3)]
    with pytest.raises(DecisionConflict):
        await decisions.approve_item(session, ref, professor, QueueApproval(process_id=SEEDED), now=NOW)
