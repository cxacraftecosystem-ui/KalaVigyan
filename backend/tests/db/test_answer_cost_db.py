from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import request_id_scope
from app.models import Answer, UsageEvent
from app.services.answering import AnswerAsk

from .write_back_seed import (
    ABSTRACT_ID,
    FIGURE_QUOTE,
    FIGURE_TEXT,
    answer,
    answer_store,
    kept_answer,
    said,
    seeded_session,
)

pytestmark = pytest.mark.db

REQUEST = "answer-cost-request-0001"
OTHER = "answer-cost-request-0002"


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in seeded_session():
        yield opened


async def test_a_finished_answer_records_what_its_request_cost_and_how_long_it_took(
    session: AsyncSession,
) -> None:
    session.add_all(
        UsageEvent(task=task, requestId=request, costUsd=cost, outcome="OK")
        for task, request, cost in (
            ("PLAN", REQUEST, Decimal("0.012500")),
            ("COMPOSE", REQUEST, Decimal("0.031000")),
            ("EMBED", REQUEST, Decimal("0.000250")),
            ("COMPOSE", OTHER, Decimal("0.900000")),
        )
    )
    await session.flush()
    ask = AnswerAsk(
        question="Why does alum keep Zelvar red?",
        depth="DETAILED",
        asked_at=datetime.now(UTC) - timedelta(seconds=3),
    )
    with request_id_scope(REQUEST):
        answer_id, _ = await kept_answer(
            answer_store(session), ask, answer(said(FIGURE_TEXT, ABSTRACT_ID, FIGURE_QUOTE))
        )
    row = await session.get(Answer, answer_id)
    await session.refresh(row)
    assert row.costUsd == Decimal("0.043750")
    assert row.latencyMs is not None and 3000 <= row.latencyMs < 120_000
