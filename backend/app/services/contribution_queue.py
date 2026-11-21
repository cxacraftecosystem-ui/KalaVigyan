from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from math import ceil

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.allowances import ALLOWANCE_UNREAD
from app.core.errors import InvalidInput
from app.core.rate_limit import FACT_PROPOSALS, proposal_slots
from app.models import QueuedProposal, User
from app.research.contribution_queue import (
    FAILED,
    QUEUED,
    BatchItem,
    ProposalBatch,
    content_key,
    proposal_fingerprint,
    subject_key,
)
from app.research.knowledge_writes import FactProposal
from app.research.trust_tiers import TrustStanding

from . import trust_tiers
from .candidate_store import proposal_subject
from .contribution_queue_tickets import ticket_of

__all__ = ["QueuedFact", "batch_of", "enqueue_facts"]

KEY_REUSED = (
    "The idempotency key {key} was given before for another fact; give each fact its own key, and the same "
    "key only when you send the same fact again."
)
KEY_TWICE = "The idempotency key {key} is given twice in this call; give each fact its own key."
SPENT = (
    "This account may propose {limit} facts an hour at its trust tier ({tier}) and has proposed them; "
    "send this fact again in about {minutes}."
)
BATCH_WORDS = (
    "{accepted} of {count} facts are in the queue ({replayed} of them sent before) and {refused} were refused; "
    "call get_proposal with each proposalId to see its gates."
)
MINUTE = 60


@dataclass(frozen=True)
class QueuedFact:
    index: int
    proposal: FactProposal
    key: str | None = None


@dataclass(frozen=True)
class _Planned:
    fact: QueuedFact
    fingerprint: str
    key: str


async def enqueue_facts(
    session: AsyncSession, proposer: User, facts: Sequence[QueuedFact], *, origin: str, now: datetime
) -> ProposalBatch:
    standing = await trust_tiers.account_standing(session, proposer.id)
    planned = [_plan(fact) for fact in facts]
    known = await _known(session, proposer.id, [plan.key for plan in planned])
    items: dict[int, BatchItem] = {}
    fresh: list[_Planned] = []
    seen: set[str] = set()
    subjects: dict[str, str | None] = {}
    for plan in planned:
        if plan.key in seen:
            items[plan.fact.index] = _refused(plan, KEY_TWICE.format(key=plan.key))
        elif plan.key in known:
            items[plan.fact.index] = await _replayed(session, plan, known[plan.key], now=now)
        elif (problem := await _subject_problem(session, plan.fact.proposal, subjects)) is not None:
            items[plan.fact.index] = _refused(plan, problem)
        else:
            fresh.append(plan)
        seen.add(plan.key)
    items |= await _queued(session, proposer, fresh, standing, origin=origin, now=now)
    return batch_of([items[fact.index] for fact in facts])


def _plan(fact: QueuedFact) -> _Planned:
    fingerprint = proposal_fingerprint(fact.proposal)
    return _Planned(fact=fact, fingerprint=fingerprint, key=fact.key or content_key(fingerprint))


async def _known(session: AsyncSession, proposer_id: uuid.UUID, keys: list[str]) -> dict[str, QueuedProposal]:
    rows = await session.scalars(
        select(QueuedProposal).where(
            QueuedProposal.proposerId == proposer_id, QueuedProposal.idempotencyKey.in_(keys)
        )
    )
    return {row.idempotencyKey: row for row in rows.all()}


async def _replayed(
    session: AsyncSession, plan: _Planned, row: QueuedProposal, *, now: datetime
) -> BatchItem:
    if row.fingerprint != plan.fingerprint:
        return _refused(plan, KEY_REUSED.format(key=plan.key))
    if row.state == FAILED:
        row.state, row.attempts, row.availableAt, row.leaseUntil = QUEUED, 0, now, None
        row.startedAt, row.finishedAt, row.failure = None, None, None
        await session.flush()
    ticket = await ticket_of(session, row, replayed=True)
    return BatchItem(index=plan.fact.index, accepted=True, idempotency_key=plan.key, ticket=ticket)


async def _subject_problem(
    session: AsyncSession, proposal: FactProposal, checked: dict[str, str | None]
) -> str | None:
    key = subject_key(proposal.subject)
    if key not in checked:
        try:
            await proposal_subject(session, proposal.subject)
            checked[key] = None
        except InvalidInput as unknown:
            checked[key] = f"{unknown}; find_crafts gives the slugs."
    return checked[key]


async def _queued(
    session: AsyncSession,
    proposer: User,
    fresh: Sequence[_Planned],
    standing: TrustStanding,
    *,
    origin: str,
    now: datetime,
) -> dict[int, BatchItem]:
    taken = await proposal_slots(FACT_PROPOSALS, proposer, len(fresh), limit=standing.facts_per_hour, now=now)
    problem = ALLOWANCE_UNREAD if taken.unread else _spent(standing, taken.wait_seconds)
    items: dict[int, BatchItem] = {}
    for number, plan in enumerate(fresh):
        if number >= taken.granted:
            items[plan.fact.index] = _refused(plan, problem)
            continue
        row, created = await _stored(
            session, proposer.id, plan, origin=origin, now=now + timedelta(microseconds=number)
        )
        ticket = await ticket_of(session, row, replayed=not created)
        items[plan.fact.index] = BatchItem(
            index=plan.fact.index, accepted=True, idempotency_key=plan.key, ticket=ticket
        )
    return items


async def _stored(
    session: AsyncSession, proposer_id: uuid.UUID, plan: _Planned, *, origin: str, now: datetime
) -> tuple[QueuedProposal, bool]:
    proposal = plan.fact.proposal
    row = QueuedProposal(
        id=uuid.uuid4(),
        proposerId=proposer_id,
        kind="FACT",
        origin=origin,
        idempotencyKey=plan.key,
        fingerprint=plan.fingerprint,
        subjectKey=subject_key(proposal.subject),
        taskKey=proposal.task_key,
        proposal=proposal.model_dump(mode="json", by_alias=True),
        state=QUEUED,
        attempts=0,
        modelCalls=0,
        costUsd=Decimal(0),
        leaseUntil=None,
        startedAt=None,
        finishedAt=None,
        outcome=None,
        reply=None,
        failure=None,
        availableAt=now,
        createdAt=now,
    )
    try:
        async with session.begin_nested():
            session.add(row)
    except IntegrityError:
        found = await _known(session, proposer_id, [plan.key])
        return found[plan.key], False
    return row, True


def _refused(plan: _Planned, problem: str) -> BatchItem:
    return BatchItem(index=plan.fact.index, accepted=False, idempotency_key=plan.key, problem=problem)


def _spent(standing: TrustStanding, wait: float) -> str:
    minutes = max(1, ceil(wait / MINUTE))
    words = "1 minute" if minutes == 1 else f"{minutes} minutes"
    return SPENT.format(limit=standing.facts_per_hour, tier=standing.tier.lower(), minutes=words)


def batch_of(items: list[BatchItem]) -> ProposalBatch:
    accepted = [item for item in items if item.accepted]
    replayed = sum(1 for item in accepted if item.ticket is not None and item.ticket.replayed)
    refused = len(items) - len(accepted)
    message = BATCH_WORDS.format(accepted=len(accepted), count=len(items), replayed=replayed, refused=refused)
    return ProposalBatch(accepted=len(accepted), refused=refused, items=items, message=message)
