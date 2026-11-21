from collections.abc import AsyncIterator
from datetime import timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AnswerGap
from app.services.answer_gap_refresh import refresh_answer_gaps

from .answer_gaps_seed import ASKERS, NEAR, NORTH, NOW, Question, asked, fact, seeded_session

pytestmark = pytest.mark.db

FIRST = ASKERS[0]
CAMEL_DUNG = "Why does Qelmor Print use camel dung?"
IN_HINDI = "क़ेल्मोर छपाई में ऊँट का गोबर क्यों डालते हैं?"
SOFTENS = "Camel dung softens the cloth before the bath."
SOAKED = "The dung of camels is soaked overnight."


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in seeded_session():
        yield opened


async def opened_gap(session: AsyncSession, question: str) -> None:
    await asked(session, Question(question, FIRST, 1))
    report = await refresh_answer_gaps(session, None, now=NOW)
    assert (report.grouped.opened, report.answered) == (1, 0)


async def answered_after(session: AsyncSession, hours: int) -> int:
    return (await refresh_answer_gaps(session, None, now=NOW + timedelta(hours=hours))).answered


async def state_of(session: AsyncSession, question: str) -> str | None:
    return await session.scalar(select(AnswerGap.state).where(AnswerGap.question == question))


async def test_facts_sharing_only_the_craft_s_name_or_common_words_leave_the_gap_open(
    session: AsyncSession,
) -> None:
    await opened_gap(session, CAMEL_DUNG)
    await fact(session, "Qelmor Print uses natural dyes.", "CHEMISTRY")
    await fact(session, "Qelmor Print is printed in Qelmor town.", "CHEMISTRY")
    assert await answered_after(session, 1) == 0
    assert await state_of(session, CAMEL_DUNG) == "OPEN"
    await fact(session, SOFTENS, "CHEMISTRY")
    await fact(session, SOAKED, "CHEMISTRY")
    assert await answered_after(session, 2) == 1
    assert await state_of(session, CAMEL_DUNG) == "ANSWERED"


async def test_facts_with_no_field_do_not_answer_a_named_field(session: AsyncSession) -> None:
    await opened_gap(session, CAMEL_DUNG)
    await fact(session, SOFTENS, None)
    await fact(session, SOAKED, None)
    assert await answered_after(session, 1) == 0
    await fact(session, SOFTENS, "HISTORY")
    await fact(session, SOAKED, "HISTORY")
    assert await answered_after(session, 2) == 0
    assert await state_of(session, CAMEL_DUNG) == "OPEN"


async def test_a_question_in_another_script_is_answered_only_by_facts_close_in_meaning(
    session: AsyncSession,
) -> None:
    await opened_gap(session, IN_HINDI)
    await fact(session, "Qelmor printers rinse the cloth in the river.", "CHEMISTRY", NORTH)
    await fact(session, "Qelmor printers dry the cloth in the sun.", "CHEMISTRY", NORTH)
    assert await answered_after(session, 1) == 0
    await fact(session, SOFTENS, "CHEMISTRY", NEAR)
    await fact(session, SOAKED, "CHEMISTRY", NEAR)
    assert await answered_after(session, 2) == 1
    assert await state_of(session, IN_HINDI) == "ANSWERED"
