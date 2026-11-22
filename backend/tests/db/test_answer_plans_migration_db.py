import uuid
from collections.abc import AsyncIterator, Callable
from typing import Any

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import Connection, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.models import Answer
from app.research.planning import RetrievalPlan
from app.research.sections import AnswerPlans, SectionPlan

from ..migration_scripts import migration

pytestmark = pytest.mark.db

STEP = migration("0014_sectioned_answer_plans")


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-answer-plans-migration/{name}")


OLD, SECTIONED, BLANK = key("old"), key("sectioned"), key("blank")
PLAN = RetrievalPlan.model_validate(
    {
        "mode": "HYBRID",
        "craft": {"slug": "Plan-Wrap-Craft", "name": "Plan Wrap Craft", "path": "/crafts/Plan-Wrap-Craft"},
        "intent": "SCIENCE",
        "language": "en",
        "needsRegion": False,
        "facets": [{"type": "MATERIAL", "target": "alum"}],
        "tiers": ["T0", "T1", "T2"],
        "maxFetches": 0,
    }
)
SEEDED = PLAN.model_dump(mode="json", by_alias=True)
SECTION_PLAN = PLAN.model_copy(update={"intent": "PROCESS"})
SECTIONED_PLANS = AnswerPlans(
    sections=[SectionPlan(section_id="s2", discipline="CHEMISTRY", plan=SECTION_PLAN)]
).model_dump(mode="json", by_alias=True)


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            opened = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
            await _seed(opened)
            yield opened
            await opened.close()
        finally:
            await transaction.rollback()


async def _seed(session: AsyncSession) -> None:
    session.add_all(
        [
            Answer(id=OLD, question="Why does alum keep the red?", mode="HYBRID", plan=SEEDED),
            Answer(id=SECTIONED, question="How is the red mordanted?", mode="HYBRID", plan=SECTIONED_PLANS),
            Answer(id=BLANK, question="Where is the red made?", mode="HYBRID"),
        ]
    )
    await session.flush()


def _within_alembic(connection: Connection, step: Callable[[], None]) -> None:
    with Operations.context(MigrationContext.configure(connection)):
        step()


async def run(session: AsyncSession, step: Callable[[], None]) -> None:
    connection = await session.connection()
    await connection.run_sync(_within_alembic, step)


async def plans(session: AsyncSession) -> dict[uuid.UUID, Any]:
    query = select(Answer.id, Answer.plan).where(Answer.id.in_((OLD, SECTIONED, BLANK)))
    return dict((await session.execute(query)).tuples().all())


async def test_an_older_plan_becomes_the_overview_section_and_other_plans_are_left_alone(
    session: AsyncSession,
) -> None:
    await run(session, STEP.upgrade)
    found = await plans(session)
    assert found == {
        OLD: {
            "schemaVersion": 1,
            "sections": [{"sectionId": "s1", "discipline": "OVERVIEW", "plan": SEEDED}],
        },
        SECTIONED: SECTIONED_PLANS,
        BLANK: None,
    }
    (section,) = AnswerPlans.model_validate(found[OLD]).sections
    assert (section.section_id, section.discipline, section.plan) == ("s1", "OVERVIEW", PLAN)


async def test_the_way_back_turns_each_plan_into_its_first_section_s_plan(session: AsyncSession) -> None:
    await run(session, STEP.upgrade)
    await run(session, STEP.downgrade)
    assert await plans(session) == {
        OLD: SEEDED,
        SECTIONED: SECTION_PLAN.model_dump(mode="json", by_alias=True),
        BLANK: None,
    }
