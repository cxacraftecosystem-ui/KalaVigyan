from collections.abc import AsyncIterator
from decimal import Decimal
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db import get_engine
from app.models import UsageEvent
from app.providers.budget import ANSWER_CAP, MONTHLY_CEILING, AnswerSpend
from app.providers.catalogue import AiTask
from app.providers.router import Principal, reserve
from app.services import app_settings

pytestmark = pytest.mark.db


@pytest.fixture
async def sessions() -> AsyncIterator[tuple[async_sessionmaker[AsyncSession], AsyncSession]]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            factory = async_sessionmaker(
                bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
            )
            async with factory() as session:
                yield factory, session
        finally:
            await transaction.rollback()


async def spent_to_the_ceiling(session: AsyncSession) -> None:
    await app_settings.set_value(session, app_settings.MONTHLY_CEILING_USD, 0.01)
    await app_settings.set_value(session, app_settings.DEGRADE_AT_FRACTION, 0.8)
    session.add(UsageEvent(task="PLAN", costUsd=Decimal("0.02"), outcome="OK", role="ADMIN"))
    await session.commit()


async def reserved(
    factory: async_sessionmaker[AsyncSession], principal: Principal, estimate: str
) -> tuple[UsageEvent, Any]:
    async with factory() as session:
        event_id, decision = await reserve(
            session, task=AiTask.PLAN, choice=None, principal=principal, estimate_usd=Decimal(estimate)
        )
        return await session.get(UsageEvent, event_id), decision


@pytest.mark.parametrize("role", ["STUDENT", "ARTISAN", "RESEARCHER", "PROFESSOR", "ADMIN", "MASTER_ADMIN"])
@pytest.mark.parametrize("depth", ["BASIC", "DETAILED", "EXPERT"])
async def test_with_no_stored_caps_every_role_and_depth_reserves_and_the_estimate_is_recorded(
    sessions: Any, role: str, depth: str
) -> None:
    factory, session = sessions
    session.add(UsageEvent(task="COMPOSE", costUsd=Decimal("5000"), outcome="OK", role=role))
    await session.commit()
    answer = AnswerSpend(depth=depth)
    main, main_decision = await reserved(factory, Principal(role=role, answer=answer), "40")
    extra, extra_decision = await reserved(factory, Principal(role=role, answer=answer.headroom()), "40")
    assert [
        (d.allowed, d.degrade, e.outcome, e.estimatedCostUsd)
        for d, e in ((main_decision, main), (extra_decision, extra))
    ] == [
        (True, False, "RESERVED", Decimal("40")),
        (True, False, "RESERVED", Decimal("40")),
    ]
    assert answer.held_usd == Decimal("80")


async def test_a_master_admin_reserves_past_the_ceiling_and_a_student_is_refused(sessions: Any) -> None:
    factory, session = sessions
    await spent_to_the_ceiling(session)
    master, master_decision = await reserved(factory, Principal(role="MASTER_ADMIN"), "0.5")
    student, student_decision = await reserved(factory, Principal(role="STUDENT"), "0.001")
    assert (master_decision.allowed, master_decision.degrade) == (True, False)
    assert (master.outcome, master.role, master.estimatedCostUsd) == (
        "RESERVED",
        "MASTER_ADMIN",
        Decimal("0.5"),
    )
    assert (student_decision.allowed, student_decision.degrade) == (False, True)
    assert (student.outcome, student.errorKind) == ("REFUSED_CEILING", MONTHLY_CEILING)


async def test_an_answer_holds_its_reservations_against_its_depth_cap(sessions: Any) -> None:
    factory, session = sessions
    caps = {"BASIC": 0.1, "DETAILED": 0.5, "EXPERT": 1.0}
    await app_settings.set_value(session, app_settings.ANSWER_CAP_USD, caps)
    await session.commit()
    answer = AnswerSpend(depth="BASIC")
    first, first_decision = await reserved(factory, Principal(role="ADMIN", answer=answer), "0.08")
    second, second_decision = await reserved(factory, Principal(role="ADMIN", answer=answer), "0.05")
    assert first_decision.allowed and first.outcome == "RESERVED"
    assert answer.held_usd == Decimal("0.08")
    assert (second_decision.allowed, second.outcome, second.errorKind) == (
        False,
        "REFUSED_CEILING",
        ANSWER_CAP,
    )
    master_answer = AnswerSpend(depth="BASIC")
    master, master_decision = await reserved(
        factory, Principal(role="MASTER_ADMIN", answer=master_answer), "5"
    )
    assert master_decision.allowed and master.outcome == "RESERVED"


async def test_optional_work_reserves_only_inside_the_answer_s_kept_half(sessions: Any) -> None:
    factory, session = sessions
    await app_settings.set_value(session, app_settings.ANSWER_CAP_USD, {"DETAILED": 0.5})
    await session.commit()
    answer = AnswerSpend(depth="DETAILED")
    _, prose_decision = await reserved(factory, Principal(role="ADMIN", answer=answer), "0.2")
    panel, panel_decision = await reserved(factory, Principal(role="ADMIN", answer=answer.headroom()), "0.1")
    _, more_decision = await reserved(factory, Principal(role="ADMIN", answer=answer), "0.1")
    assert prose_decision.allowed and more_decision.allowed
    assert (panel_decision.allowed, panel.outcome, panel.errorKind) == (False, "REFUSED_CEILING", ANSWER_CAP)
    assert answer.held_usd == Decimal("0.3")
    master_answer = AnswerSpend(depth="DETAILED")
    master, master_decision = await reserved(
        factory, Principal(role="MASTER_ADMIN", answer=master_answer.headroom()), "5"
    )
    assert master_decision.allowed and master.outcome == "RESERVED"
    assert master_answer.held_usd == Decimal("5")
