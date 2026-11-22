import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.models import Answer
from app.services.builder_record import BUILDS_KEY, BuilderOutcome, answer_build_record

pytestmark = pytest.mark.db

READING_STYLE = {"readingStyle": None}


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            opened = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
            yield opened
            await opened.close()
        finally:
            await transaction.rollback()


async def test_each_section_s_builders_are_added_to_the_answer_s_plan(session: AsyncSession) -> None:
    answer_id = uuid.uuid4()
    session.add(Answer(id=answer_id, question="Why is Khurja glaze blue?", mode="DEEP", plan=READING_STYLE))
    await session.flush()

    def sessions() -> AsyncSession:
        return AsyncSession(bind=session.bind, expire_on_commit=False, autoflush=False)

    record = answer_build_record(sessions)
    await record(answer_id, "s2", [BuilderOutcome("simulation", "OUT_OF_TIME", 0, 60.04)])
    await record(answer_id, "s3", [BuilderOutcome("simulation", "NO_QUANTITY", 2, 0.31)])
    plan = await session.scalar(select(Answer.plan).where(Answer.id == answer_id))
    assert plan is not None and plan["readingStyle"] is None
    assert plan[BUILDS_KEY] == [
        {"sectionId": "s2", "kind": "simulation", "outcome": "OUT_OF_TIME", "blocks": 0, "seconds": 60.0},
        {"sectionId": "s3", "kind": "simulation", "outcome": "NO_QUANTITY", "blocks": 2, "seconds": 0.3},
    ]
