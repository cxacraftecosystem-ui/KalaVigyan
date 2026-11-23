import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AuditLog,
    Claim,
    ClaimSource,
    Concept,
    ConditionReading,
    Craft,
    Process,
    ProcessCondition,
    ProcessStage,
    Source,
    User,
)
from app.research.review_queue import QueueApproval, QueueRejection, ReadingQueueItem, ReviewFilters
from app.services.craft_process import process_records
from app.services.open_work import review_queues
from app.services.review_queue import QueueAdapters, list_review_queue
from app.services.review_queue_decisions import ItemRef, approve_item, reject_item
from app.services.review_queue_errors import OwnItem

from .review_queue_seed import TurnsOf
from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 23, 12, tzinfo=UTC)
SLUG = "Reading-Review-Test-Craft"
ADAPTERS = QueueAdapters(objects=None, turns_of=TurnsOf())
STATEMENT = "The madder bath of this test craft is boiled at 130 °C for an hour."


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-reading-review/{name}")


CRAFT, CONCEPT, CLAIM, SOURCE, CITED = key("craft"), key("concept"), key("claim"), key("source"), key("cited")
PROCESS, STAGE, CONDITION, HOT, WARM = key("process"), key("stage"), key("condition"), key("hot"), key("warm")


@dataclass(frozen=True)
class People:
    writer: User
    reviewer: User


@pytest.fixture
async def seeded() -> AsyncIterator[tuple[AsyncSession, People]]:
    async for session in rolled_back_session():
        people = People(_person("writer"), _person("reviewer"))
        session.add_all([people.writer, people.reviewer])
        session.add(Craft(id=CRAFT, slug=SLUG, name="Reading Review Test Craft"))
        session.add(
            Source(id=SOURCE, kind="PAPER", title="Madder baths", licence="CC-BY-4.0", reliability="B")
        )
        await session.flush()
        await _fact(session, people.writer)
        await _process(session)
        yield session, people


def _person(name: str) -> User:
    return User(id=key(name), name=name.title(), email=f"{name}-reading@example.org", role="PROFESSOR")


async def _fact(session: AsyncSession, writer: User) -> None:
    session.add(Concept(id=CONCEPT, craftId=CRAFT, type="PROCESS_STAGE", name="Madder bath"))
    await session.flush()
    session.add(
        Claim(
            id=CLAIM,
            subjectType="CONCEPT",
            subjectId=CONCEPT,
            predicate="states",
            text=STATEMENT,
            evidenceLevel="PROVISIONAL",
            origin="RESEARCHER",
            status="APPROVED",
            field="CHEMISTRY",
            createdById=writer.id,
            createdByKind="USER",
        )
    )
    await session.flush()
    session.add(
        ClaimSource(
            id=CITED,
            claimId=CLAIM,
            sourceId=SOURCE,
            quote="boiled at 130 °C",
            locator="p. 2",
            quoteCheck="PASS",
        )
    )
    await session.flush()


async def _process(session: AsyncSession) -> None:
    session.add(Process(id=PROCESS, craftId=CRAFT, name="Dyeing"))
    await session.flush()
    session.add(ProcessStage(id=STAGE, processId=PROCESS, ordinal=1, name="Madder bath", stageType="DYE"))
    await session.flush()
    session.add(
        ProcessCondition(
            id=CONDITION,
            stageId=STAGE,
            key="bath-temperature",
            label="Bath temperature",
            quantity="TEMPERATURE",
        )
    )
    await session.flush()
    session.add_all([_reading(HOT, "130 °C", Decimal(130)), _reading(WARM, "60 °C", Decimal(60))])
    await session.flush()


def _reading(reading_id: uuid.UUID, stated: str, value: Decimal) -> ConditionReading:
    return ConditionReading(
        id=reading_id,
        conditionId=CONDITION,
        claimSourceId=CITED,
        stated=stated,
        statedMin=value,
        statedMax=value,
        statedUnit="°C",
    )


async def readings_for(session: AsyncSession, viewer: User) -> list[ReadingQueueItem]:
    page = await list_review_queue(
        session, viewer, ReviewFilters(kind="READINGS", craft_slug=SLUG), adapters=ADAPTERS, now=NOW
    )
    return [item for item in page.items if isinstance(item, ReadingQueueItem)]


async def test_only_a_reading_outside_its_stage_s_range_waits_for_a_reviewer_who_did_not_write_it(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    (item,) = await readings_for(session, people.reviewer)
    review = item.reading
    assert (item.id, item.origin, item.craft.slug if item.craft else None) == (
        HOT,
        "RESEARCH",
        "Reading-Review-Test-Craft",
    )
    assert (review.stated, review.min, review.max, review.unit) == ("130 °C", 130.0, 130.0, "°C")
    assert (review.envelope_min, review.envelope_max, review.stage_type) == (20.0, 100.0, "DYE")
    assert (review.condition, review.stage, review.statement) == (
        "Bath temperature",
        "Madder bath",
        STATEMENT,
    )
    assert [source.title for source in review.sources] == ["Madder baths"]
    assert await readings_for(session, people.writer) == []
    standing = (await review_queues(session, ["READINGS"]))["READINGS"]
    assert standing.count == 1


async def test_a_rejected_reading_leaves_the_queue_and_the_process_with_its_reason_kept(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    decided = await reject_item(
        session, ItemRef("READINGS", HOT), people.reviewer, QueueRejection(reason="Misread: 13 °C."), now=NOW
    )
    assert (decided.kind, decided.status) == ("READINGS", "REJECTED")
    row = await session.get(ConditionReading, HOT)
    assert row is not None
    assert (row.reviewStatus, row.reviewedById, row.reviewNote) == (
        "REJECTED",
        people.reviewer.id,
        "Misread: 13 °C.",
    )
    assert await readings_for(session, people.reviewer) == []
    craft = await session.get(Craft, CRAFT)
    assert craft is not None
    records = await process_records(session, craft)
    assert [reading.stated for condition in records.conditions for reading in condition.readings] == ["60 °C"]
    actions = await session.scalars(select(AuditLog.action).where(AuditLog.targetId == str(HOT)))
    assert actions.all() == ["review.reading_rejected"]


async def test_an_approved_reading_stays_shown_and_the_writer_cannot_decide_their_own(
    seeded: tuple[AsyncSession, People],
) -> None:
    session, people = seeded
    with pytest.raises(OwnItem):
        await approve_item(session, ItemRef("READINGS", HOT), people.writer, QueueApproval(), now=NOW)
    decided = await approve_item(session, ItemRef("READINGS", HOT), people.reviewer, QueueApproval(), now=NOW)
    assert decided.status == "APPROVED"
    craft = await session.get(Craft, CRAFT)
    assert craft is not None
    records = await process_records(session, craft)
    shown = sorted(reading.stated for condition in records.conditions for reading in condition.readings)
    assert shown == ["130 °C", "60 °C"]
    assert await readings_for(session, people.reviewer) == []
