import uuid
from collections.abc import AsyncIterator
from datetime import date, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import QueuedProposal, UsageEvent, User
from app.research.contribution_queue import proposal_fingerprint, stream_request_id
from app.research.cost_ledger import LedgerRange
from app.services.cost_ledger import cost_ledger, stream_spend

from .contribution_seed import NOW, fact, person, seeded_session

pytestmark = pytest.mark.db

FIRST = uuid.uuid5(uuid.NAMESPACE_URL, "test-cost-ledger/first")
SECOND = uuid.uuid5(uuid.NAMESPACE_URL, "test-cost-ledger/second")
THIRD = uuid.uuid5(uuid.NAMESPACE_URL, "test-cost-ledger/third")
NEXT_DAY = NOW + timedelta(days=1)


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in seeded_session():
        yield opened


def call(
    user: User, task: str, cost: str, *, request_id: str, at: datetime, outcome: str = "OK"
) -> UsageEvent:
    return UsageEvent(
        userId=user.id,
        role=user.role,
        task=task,
        provider="ANTHROPIC" if task == "EVAL_JUDGE" else "GEMINI",
        model="claude-haiku-5-5" if task == "EVAL_JUDGE" else "gemini-embedding-2",
        costUsd=Decimal(cost),
        outcome=outcome,
        requestId=request_id,
        createdAt=at,
    )


def checked(user: User, proposal_id: uuid.UUID, finished: datetime) -> QueuedProposal:
    proposal = fact()
    return QueuedProposal(
        id=proposal_id,
        proposerId=user.id,
        origin="AGENT",
        idempotencyKey=f"ledger:{proposal_id.hex}",
        fingerprint=proposal_fingerprint(proposal),
        subjectKey="craft:ledger",
        proposal=proposal.model_dump(mode="json", by_alias=True),
        state="DONE",
        outcome="WAITING",
        attempts=1,
        availableAt=finished,
        finishedAt=finished,
        createdAt=finished,
    )


async def streams(session: AsyncSession, researcher: User, other: User) -> None:
    first, second, third = stream_request_id(FIRST), stream_request_id(SECOND), stream_request_id(THIRD)
    session.add_all(
        [
            call(researcher, "EMBED", "0.000100", request_id=first, at=NOW),
            call(researcher, "EVAL_JUDGE", "0.002000", request_id=first, at=NOW),
            call(researcher, "EVAL_JUDGE", "0", request_id=first, at=NOW, outcome="ERROR"),
            call(researcher, "EMBED", "0.000100", request_id=second, at=NEXT_DAY),
            call(other, "EVAL_JUDGE", "0.500000", request_id=third, at=NOW),
            call(researcher, "COMPOSE", "1.000000", request_id="answer-request-0001", at=NOW),
            checked(researcher, FIRST, NOW),
            checked(researcher, SECOND, NEXT_DAY),
        ]
    )
    await session.flush()


async def test_every_model_call_of_a_stream_is_ledgered_per_account_and_day(session: AsyncSession) -> None:
    researcher = await person(session, "RESEARCHER")
    other = await person(session, "RESEARCHER")
    await streams(session, researcher, other)
    ledger = await cost_ledger(session, LedgerRange(day_from=date(2026, 11, 20), day_to=date(2026, 11, 21)))
    assert ledger.time_zone == "Asia/Kolkata"
    assert [
        (
            item.day,
            item.user_id,
            item.proposals,
            item.calls,
            item.judge_calls,
            item.embed_calls,
            item.failures,
            item.cost_usd,
        )
        for item in ledger.days
    ] == [
        (date(2026, 11, 20), other.id, 0, 1, 1, 0, 0, 0.5),
        (date(2026, 11, 20), researcher.id, 1, 3, 2, 1, 1, 0.0021),
        (date(2026, 11, 21), researcher.id, 1, 1, 0, 1, 0, 0.0001),
    ]
    assert [(total.user_id, total.proposals, total.calls, total.cost_usd) for total in ledger.accounts] == [
        (other.id, 0, 1, 0.5),
        (researcher.id, 2, 4, 0.0022),
    ]
    assert (ledger.calls, ledger.cost_usd) == (5, 0.5022)
    assert await stream_spend(session, FIRST) == (3, Decimal("0.002100"))


def test_a_ledger_covers_a_forward_range_of_at_most_ninety_two_days() -> None:
    with pytest.raises(ValueError, match="ends before it starts"):
        LedgerRange(day_from=date(2026, 11, 20), day_to=date(2026, 11, 19))
    with pytest.raises(ValueError, match="at most 92 days"):
        LedgerRange(day_from=date(2026, 8, 1), day_to=date(2026, 11, 1))
    assert LedgerRange(day_from=date(2026, 8, 2), day_to=date(2026, 11, 1)).day_to == date(2026, 11, 1)
