import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Answer, AnswerGap, AnswerVerdict, TaskReservation
from app.research.open_work import OpenTask, Viewer, WorkFilters
from app.research.open_work_gaps import FieldReading
from app.research.sections import AnswerPlans
from app.services.answer_gap_refresh import refresh_answer_gaps
from app.services.open_work import list_open_work
from app.services.task_reservations import claim_task

from .answer_gaps_seed import (
    ASKERS,
    CRAFT,
    FAILED,
    NEAR,
    NORTH,
    NOW,
    OTHER_CRAFT,
    RESEARCHER,
    SITE,
    SLUG,
    Question,
    asked,
    fact,
    seeded_session,
)
from .write_back_seed import answer_store

pytestmark = pytest.mark.db

FIRST, SECOND, THIRD = ASKERS


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in seeded_session():
        yield opened


async def gap_of(session: AsyncSession, question: str) -> AnswerGap:
    gap = await session.scalar(select(AnswerGap).where(AnswerGap.question == question))
    assert gap is not None
    return gap


async def gap_tasks(session: AsyncSession, slug: str = SLUG) -> list[OpenTask]:
    work = await list_open_work(
        session, WorkFilters(craft_slug=slug, kind="ANSWER_GAP"), Viewer(), site=SITE, now=NOW
    )
    return work.tasks


async def test_a_finished_answer_keeps_its_verdict_its_fields_and_its_craft(session: AsyncSession) -> None:
    answer = uuid.uuid4()
    session.add(
        Answer(id=answer, userId=FIRST, question="Why is qelmorant boiled?", mode="HYBRID", craftId=CRAFT)
    )
    await session.flush()
    readings = [FieldReading("CHEMISTRY", 1, claim_ids=(FAILED,)), FieldReading("HISTORY", 4)]
    await answer_store(session).finish(
        answer,
        asked_at=datetime.now(UTC),
        plans=AnswerPlans(sections=[]),
        claim_ids=[FAILED],
        explainer=None,
        readings=readings,
    )
    verdict = await session.scalar(select(AnswerVerdict).where(AnswerVerdict.answerId == answer))
    assert verdict is not None
    assert (
        verdict.verdict,
        verdict.craftId,
        verdict.fields,
        verdict.lacking,
        verdict.lacks,
        verdict.sentences,
    ) == (
        "THIN",
        CRAFT,
        ["CHEMISTRY", "HISTORY"],
        ["CHEMISTRY"],
        ["FEW_SENTENCES", "FAILED_QUOTE"],
        5,
    )
    assert verdict.gapId is None and verdict.embedding is None


FOUNDER = Question("Why is qelmorant boiled twice?", FIRST, days_ago=3)
APART = Question(
    "When did the qelmor printers start?",
    THIRD,
    days_ago=1,
    vector=NORTH,
    lacking=("HISTORY",),
    lacks=("LOW_RETRIEVAL",),
)
JOINING = Question(
    "What does boiling qelmorant twice do?",
    SECOND,
    days_ago=1,
    vector=NEAR,
    verdict="UNANSWERED",
    lacking=("CHEMISTRY", "HISTORY"),
    lacks=("NO_CITED_EVIDENCE",),
)
ASKED_SEVEN_TIMES = (
    FOUNDER,
    Question("Why do printers boil qelmorant two times?", FIRST, days_ago=2),
    JOINING,
    APART,
    Question("Why is qelmorant boiled twice in weaving?", THIRD, days_ago=1, craft=OTHER_CRAFT),
    Question("Why is qelmorant boiled at all?", SECOND, days_ago=100),
    Question("What colour is qelmorant?", SECOND, days_ago=1, verdict="ANSWERED"),
)


@pytest.fixture
async def grouped(session: AsyncSession) -> dict[str, object]:
    for question in ASKED_SEVEN_TIMES:
        await asked(session, question)
    return (await refresh_answer_gaps(session, None, now=NOW)).as_dict()


async def test_thin_questions_group_by_craft_and_meaning_and_count_each_reader_once(
    session: AsyncSession, grouped: dict[str, object]
) -> None:
    counted = {key: grouped[key] for key in ("questions", "dropped", "joined", "opened", "answered")}
    assert counted == {"questions": 5, "dropped": 0, "joined": 2, "opened": 3, "answered": 0}
    gap = await gap_of(session, FOUNDER.text)
    assert (gap.askers, gap.fields, gap.lacks, gap.priority, gap.state) == (
        2,
        ["CHEMISTRY", "HISTORY"],
        ["NO_CITED_EVIDENCE", "FEW_SENTENCES"],
        "MEDIUM",
        "OPEN",
    )
    assert gap.lastAskedAt == NOW - timedelta(days=1)


async def test_each_group_is_one_task_of_its_craft_by_how_many_asked(
    session: AsyncSession, grouped: dict[str, object]
) -> None:
    founded, alone = await gap_of(session, FOUNDER.text), await gap_of(session, APART.text)
    tasks = await gap_tasks(session)
    assert [task.key for task in tasks] == [
        f"ANSWER_GAP:craft:{SLUG}:gap-{founded.id.hex}",
        f"ANSWER_GAP:craft:{SLUG}:gap-{alone.id.hex}",
    ]
    assert [(task.priority, task.count, task.field, task.prompt) for task in tasks] == [
        ("MEDIUM", 2, "CHEMISTRY", "research_field"),
        ("LOW", 1, "HISTORY", "research_field"),
    ]
    assert tasks[0].needed == (
        'Readers asked "Why is qelmorant boiled twice?" (2 readers in the last 90 days, the latest on 2026-11-18); '
        "the answer found no cited evidence and held fewer than 3 cited sentences in a field. "
        "Cited facts under CHEMISTRY and HISTORY would answer it."
    )
    assert [task.key.split(":")[2] for task in await gap_tasks(session, "Qelmor-Weave")] == ["Qelmor-Weave"]


async def test_the_asker_never_appears_and_a_question_about_a_person_is_dropped(
    session: AsyncSession,
) -> None:
    await asked(
        session,
        Question("My name is Priya Asker, priya.asker@example.org: why is qelmorant boiled twice?", FIRST, 1),
    )
    await asked(session, Question("What is the phone number of the qelmor printer in Bhuj?", SECOND, 1))
    report = await refresh_answer_gaps(session, None, now=NOW)
    assert (report.grouped.candidates, report.grouped.dropped, report.grouped.opened) == (2, 1, 1)
    (task,) = await gap_tasks(session)
    shown = task.model_dump_json(by_alias=True)
    assert task.needed.startswith(
        'Readers asked "My name is [name], [email]: why is qelmorant boiled twice?" (1 '
    )
    for private in ("Priya", "priya.asker@example.org", str(FIRST), FIRST.hex, "phone number"):
        assert private not in shown
    answers = (await session.scalars(select(Answer.id).where(Answer.userId == FIRST))).all()
    assert all(str(answer) not in shown and answer.hex not in shown for answer in answers)


async def test_a_gap_whose_facts_arrive_closes_itself_and_completes_its_reservation(
    session: AsyncSession,
) -> None:
    question = Question(
        "Why is qelmorant boiled twice?", FIRST, 1, lacking=("CHEMISTRY", "HISTORY"), lacks=("FEW_SENTENCES",)
    )
    await asked(session, question)
    await refresh_answer_gaps(session, None, now=NOW)
    (task,) = await gap_tasks(session)
    held = await claim_task(session, RESEARCHER, task.key, site=SITE, now=NOW)
    assert held.held and held.task is not None and held.task.key == task.key
    await fact(session, "Qelmorant is boiled twice so the red binds to the cotton.", "CHEMISTRY")
    await fact(session, "Boiled qelmorant releases the earth that holds the red.", "CHEMISTRY")
    await fact(session, "Printers first boiled qelmorant twice in 1890.", "HISTORY")
    report = await refresh_answer_gaps(session, None, now=NOW)
    assert (report.answered, report.reservations_closed) == (0, 0)
    await fact(session, "The second qelmorant boil came with the river trade.", "HISTORY")
    report = await refresh_answer_gaps(session, None, now=NOW + timedelta(hours=1))
    assert (report.answered, report.reservations_closed, report.open) == (1, 1, 0)
    gap = await gap_of(session, question.text)
    assert (gap.state, gap.closedAt) == ("ANSWERED", NOW + timedelta(hours=1))
    reservation = await session.scalar(select(TaskReservation).where(TaskReservation.taskKey == task.key))
    assert reservation is not None and reservation.ending == "COMPLETED"
    assert await gap_tasks(session) == []


async def test_a_gap_no_one_asked_within_ninety_days_lapses(session: AsyncSession) -> None:
    await asked(session, Question("Why is qelmorant boiled twice?", FIRST, 80))
    await refresh_answer_gaps(session, None, now=NOW)
    later = NOW + timedelta(days=11)
    report = await refresh_answer_gaps(session, None, now=later)
    assert (report.lapsed, report.open) == (1, 0)
    gap = await gap_of(session, "Why is qelmorant boiled twice?")
    assert (gap.state, gap.askers, gap.closedAt) == ("LAPSED", 0, later)
