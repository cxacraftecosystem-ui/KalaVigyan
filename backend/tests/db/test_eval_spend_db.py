from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import UsageEvent
from app.providers.router import tagged_settled_spend, tagged_spend

QUESTION = "answer-eval-5d57bc9c5c754e1b-q001"
SETTLED_ROWS = (
    ("COMPOSE", "claude-opus-5-5", Decimal("0.755120")),
    ("COMPOSE", "claude-sonnet-5-5", Decimal("0.149110")),
    ("EVAL_JUDGE", "claude-opus-5-5", Decimal("0.140040")),
    ("PLAN", "gemini-3.5-flash-lite", Decimal("0.004496")),
    ("RERANK", "rerank-3", Decimal("0.002144")),
    ("EMBED", "gemini-embedding-2", Decimal("0.000727")),
    ("UNDERSTAND", "gemini-3.5-flash-lite", Decimal("0.000436")),
)
LOST_ESTIMATE = Decimal("1.283412")


async def test_the_evaluation_counts_what_its_question_settled_not_an_estimate_left_reserved(
    session: AsyncSession,
) -> None:
    now = datetime.now(UTC)
    session.add_all(
        UsageEvent(task=task, model=model, requestId=QUESTION, costUsd=cost, outcome="OK", createdAt=now)
        for task, model, cost in SETTLED_ROWS
    )
    session.add(
        UsageEvent(
            task="COMPOSE",
            model="claude-sonnet-5-5",
            requestId=QUESTION,
            costUsd=Decimal(0),
            estimatedCostUsd=LOST_ESTIMATE,
            outcome="RESERVED",
            createdAt=now,
        )
    )
    await session.flush()
    since = now - timedelta(minutes=5)
    assert await tagged_spend(session, request_id_prefix=QUESTION, since=since) == Decimal("2.335485")
    assert await tagged_settled_spend(session, request_id_prefix=QUESTION, since=since) == Decimal("1.052073")
    assert await tagged_settled_spend(session, request_id_prefix="answer-eval-other", since=since) == Decimal(
        0
    )
