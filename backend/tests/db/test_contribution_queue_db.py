from collections.abc import AsyncIterator
from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ExternalFailure
from app.core.rate_limit import FACT_PROPOSALS, proposal_attempt
from app.models import Claim, QueuedProposal, User
from app.research.contribution_queue import ProposalBatch
from app.research.knowledge_writes import STATEMENT_MAX_CHARS
from app.services.contribution_queue import QueuedFact, enqueue_facts
from app.services.contribution_queue_tickets import own_ticket
from app.services.contribution_queue_worker import claim_next, drain

from ..knowledge_writes.fakes import STATEMENT
from .contribution_seed import NOW, adapters, fact, person, same_session, seeded_session

pytestmark = pytest.mark.db

OTHER_STATEMENT = "Ajrakh printers wash the cloth in running water after every dye bath they give it."


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in seeded_session():
        yield opened


async def queued(session: AsyncSession, user: User, *facts: QueuedFact) -> ProposalBatch:
    return await enqueue_facts(session, user, list(facts), origin="AGENT", now=NOW)


async def rows(session: AsyncSession) -> int:
    return int(await session.scalar(select(func.count(QueuedProposal.id))) or 0)


async def test_a_fact_is_queued_at_once_and_a_retry_with_its_key_never_doubles_it(
    session: AsyncSession,
) -> None:
    researcher = await person(session, "RESEARCHER")
    first = await queued(session, researcher, QueuedFact(0, fact(), "agent-run-1:a"))
    (item,) = first.items
    assert item.ticket is not None
    assert (item.ticket.state, item.ticket.replayed, item.ticket.position, item.ticket.attempts) == (
        "QUEUED",
        False,
        0,
        0,
    )
    again = await queued(session, researcher, QueuedFact(0, fact(), "agent-run-1:a"))
    assert again.items[0].ticket is not None and again.items[0].ticket.replayed is True
    assert again.items[0].ticket.proposal_id == item.ticket.proposal_id
    reused = await queued(session, researcher, QueuedFact(0, fact(OTHER_STATEMENT), "agent-run-1:a"))
    assert reused.items[0].accepted is False and "was given before for another fact" in str(
        reused.items[0].problem
    )
    assert await rows(session) == 1


async def test_without_a_key_the_fact_s_own_content_is_its_key(session: AsyncSession) -> None:
    researcher = await person(session, "RESEARCHER")
    first = (await queued(session, researcher, QueuedFact(0, fact()))).items[0]
    second = (await queued(session, researcher, QueuedFact(0, fact()))).items[0]
    assert first.ticket is not None and second.ticket is not None
    assert first.idempotency_key is not None and first.idempotency_key.startswith("fact:")
    assert (second.ticket.proposal_id, second.ticket.replayed) == (first.ticket.proposal_id, True)


async def test_a_batch_queues_each_good_fact_and_refuses_each_other_one_on_its_own(
    session: AsyncSession,
) -> None:
    researcher = await person(session, "RESEARCHER")
    batch = await queued(
        session,
        researcher,
        QueuedFact(0, fact(), "batch-run:one"),
        QueuedFact(1, fact(subject={"kind": "craft", "slug": "No-Such-Craft-Anywhere"}), "batch-run:two"),
        QueuedFact(2, fact(OTHER_STATEMENT), "batch-run:one"),
        QueuedFact(3, fact(OTHER_STATEMENT), "batch-run:four"),
    )
    assert (batch.accepted, batch.refused) == (2, 2)
    assert [item.accepted for item in batch.items] == [True, False, False, True]
    assert "No craft has the slug" in str(batch.items[1].problem)
    assert "given twice in this call" in str(batch.items[2].problem)
    assert batch.items[3].ticket is not None and batch.items[3].ticket.position == 1


async def test_the_worker_runs_the_gates_off_the_request_and_keeps_the_reply(session: AsyncSession) -> None:
    researcher = await person(session, "RESEARCHER")
    (item,) = (await queued(session, researcher, QueuedFact(0, fact(), "worker-run:a"))).items
    assert item.ticket is not None
    worked = await drain(lambda: same_session(session), lambda user: adapters(), clock=lambda: NOW)
    assert worked == 1
    done = await own_ticket(session, researcher, item.ticket.proposal_id)
    assert (done.state, done.outcome, done.attempts, done.finished_at, done.model_calls) == (
        "DONE",
        "WAITING",
        1,
        NOW,
        0,
    )
    assert done.reply is not None and [gate.gate for gate in done.reply.gates] == [
        "QUOTES",
        "SOURCE",
        "DUPLICATE",
        "NOVELTY",
    ]
    claim = await session.get(Claim, done.reply.claim_id)
    assert claim is not None and (claim.status, claim.createdById) == ("DRAFT", researcher.id)
    assert done.message == done.reply.message


async def test_a_check_that_cannot_run_waits_longer_each_time_then_fails_and_a_retry_queues_it_again(
    session: AsyncSession,
) -> None:
    researcher = await person(session, "RESEARCHER")
    (item,) = (await queued(session, researcher, QueuedFact(0, fact(), "outage-run:a"))).items
    assert item.ticket is not None
    down = adapters(fetched=ExternalFailure("the fetcher is down", kind="unavailable", retryable=True))
    moment = [NOW]
    await drain(lambda: same_session(session), lambda user: down, clock=lambda: moment[0])
    waiting = await own_ticket(session, researcher, item.ticket.proposal_id)
    assert (waiting.state, waiting.attempts, waiting.next_try_at) == (
        "QUEUED",
        1,
        NOW + timedelta(seconds=30),
    )
    assert "the fetcher is down" in waiting.message
    assert await drain(lambda: same_session(session), lambda user: down, clock=lambda: moment[0]) == 0
    for wait in (30, 60, 120, 240):
        moment[0] += timedelta(seconds=wait)
        await drain(lambda: same_session(session), lambda user: down, clock=lambda: moment[0])
    failed = await own_ticket(session, researcher, item.ticket.proposal_id)
    assert (failed.state, failed.attempts, failed.outcome) == ("FAILED", 5, None)
    assert list(await session.scalars(select(Claim.id).where(Claim.createdById == researcher.id))) == []
    retried = (await queued(session, researcher, QueuedFact(0, fact(), "outage-run:a"))).items[0]
    assert retried.ticket is not None and (retried.ticket.state, retried.ticket.attempts) == ("QUEUED", 0)


async def test_one_subject_is_checked_one_proposal_at_a_time(session: AsyncSession) -> None:
    researcher = await person(session, "RESEARCHER")
    category = {"kind": "category", "slug": "contribution-queue-category"}
    await queued(
        session,
        researcher,
        QueuedFact(0, fact(), "subject-run:a"),
        QueuedFact(1, fact(OTHER_STATEMENT), "subject-run:b"),
        QueuedFact(2, fact(OTHER_STATEMENT, subject=category), "subject-run:c"),
    )
    later = NOW + timedelta(seconds=1)
    first = await claim_next(session, now=later)
    second = await claim_next(session, now=later)
    third = await claim_next(session, now=later)
    keys = {
        row.id: row.idempotencyKey
        for row in await session.scalars(select(QueuedProposal).execution_options(populate_existing=True))
    }
    assert (keys[first], keys[second], third) == ("subject-run:a", "subject-run:c", None)  # type: ignore[index]


async def test_the_hour_s_allowance_refuses_the_facts_beyond_it(session: AsyncSession) -> None:
    researcher = await person(session, "RESEARCHER")
    for _ in range(29):
        assert proposal_attempt(FACT_PROPOSALS, researcher)[0] is True
    statements = [STATEMENT, OTHER_STATEMENT, OTHER_STATEMENT.replace("running", "flowing")]
    assert all(len(text) <= STATEMENT_MAX_CHARS for text in statements)
    batch = await queued(
        session,
        researcher,
        *(QueuedFact(n, fact(text), f"allowance-run:{n:03d}") for n, text in enumerate(statements)),
    )
    assert [item.accepted for item in batch.items] == [True, False, False]
    assert "may propose 30 facts an hour at its trust tier (new)" in str(batch.items[1].problem)
