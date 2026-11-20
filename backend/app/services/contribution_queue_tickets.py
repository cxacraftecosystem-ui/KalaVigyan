from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.core.roles import ADMIN, has_rank
from app.models import QueuedProposal, User
from app.research.contribution_queue import (
    CHECKING,
    DONE,
    FAILED,
    QUEUED,
    RECENT_PROPOSALS_MAX,
    ProposalTicket,
    ProposalTickets,
)
from app.research.knowledge_writes import FactProposal, ProposalReply

__all__ = ["NOT_YOURS", "own_ticket", "queue_position", "recent_tickets", "ticket_of"]

NOT_YOURS = "No proposal of this account has the id {proposal_id}; propose_facts and my_work give the ids."
QUEUED_WORDS = (
    "Queued: {ahead} proposals are ahead of it. The gates run off the request; call get_proposal with this "
    "proposalId to see them finish."
)
RETRY_WORDS = "The checks could not run on try {attempts} ({failure}); it is queued again and runs from {when:%H:%M} UTC."
CHECKING_WORDS = "The gates are checking it now (try {attempts}); call get_proposal again in a minute."
FAILED_WORDS = (
    "Not checked: the checks could not run after {attempts} tries ({failure}); nothing was stored. Send it "
    "again with the same idempotency key to queue it once more."
)


async def ticket_of(
    session: AsyncSession, row: QueuedProposal, *, replayed: bool = False, notices: Sequence[str] = ()
) -> ProposalTicket:
    proposal = FactProposal.model_validate(row.proposal)
    position = await queue_position(session, row) if row.state == QUEUED else None
    reply = ProposalReply.model_validate(row.reply) if row.reply is not None else None
    retrying = row.state == QUEUED and row.attempts > 0
    return ProposalTicket(
        proposal_id=row.id,
        state=row.state,
        idempotency_key=row.idempotencyKey,
        replayed=replayed,
        subject=proposal.subject,
        field=proposal.field,
        statement=proposal.statement,
        task_key=proposal.task_key,
        position=position,
        attempts=row.attempts,
        queued_at=row.createdAt,
        started_at=row.startedAt,
        finished_at=row.finishedAt,
        next_try_at=row.availableAt if retrying else None,
        outcome=row.outcome,
        reply=reply,
        model_calls=row.modelCalls,
        cost_usd=float(row.costUsd),
        message=_said(row, position, reply),
        notices=list(notices),
    )


async def queue_position(session: AsyncSession, row: QueuedProposal) -> int:
    ahead = await session.scalar(
        select(func.count(QueuedProposal.id)).where(
            QueuedProposal.state == QUEUED,
            tuple_(QueuedProposal.availableAt, QueuedProposal.createdAt, QueuedProposal.id)
            < tuple_(row.availableAt, row.createdAt, row.id),
        )
    )
    return int(ahead or 0)


async def own_ticket(session: AsyncSession, user: User, proposal_id: uuid.UUID) -> ProposalTicket:
    row = await session.get(QueuedProposal, proposal_id)
    if row is None or (row.proposerId != user.id and not has_rank(user, ADMIN)):
        raise InvalidInput(NOT_YOURS.format(proposal_id=proposal_id))
    return await ticket_of(session, row)


async def recent_tickets(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    limit: int = RECENT_PROPOSALS_MAX,
    since: datetime | None = None,
) -> ProposalTickets:
    statement = select(QueuedProposal).where(QueuedProposal.proposerId == user_id)
    if since is not None:
        statement = statement.where(QueuedProposal.createdAt >= since)
    rows = await session.scalars(
        statement.order_by(QueuedProposal.createdAt.desc(), QueuedProposal.id).limit(
            min(limit, RECENT_PROPOSALS_MAX)
        )
    )
    return ProposalTickets(proposals=[await ticket_of(session, row) for row in rows.all()])


def _said(row: QueuedProposal, position: int | None, reply: ProposalReply | None) -> str:
    if row.state == DONE and reply is not None:
        return reply.message
    if row.state == CHECKING:
        return CHECKING_WORDS.format(attempts=row.attempts)
    if row.state == FAILED:
        return FAILED_WORDS.format(attempts=row.attempts, failure=row.failure or "no reason was kept")
    if row.attempts > 0:
        return RETRY_WORDS.format(
            attempts=row.attempts,
            failure=row.failure or "no reason was kept",
            when=row.availableAt.astimezone(UTC),
        )
    return QUEUED_WORDS.format(ahead=position or 0)
