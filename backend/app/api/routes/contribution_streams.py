from __future__ import annotations

import uuid
from collections.abc import Awaitable
from datetime import UTC, date, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import INDIA_TZ
from app.core.config import get_settings
from app.core.db import get_session
from app.core.deps import require
from app.core.errors import InvalidInput, Refused
from app.core.roles import Capability
from app.models import User
from app.research.base import ContractModel
from app.research.contribution_queue import (
    RECENT_PROPOSALS_MAX,
    FactBatchBody,
    ProposalBatch,
    ProposalTicket,
    ProposalTickets,
)
from app.research.cost_ledger import LEDGER_DAYS_DEFAULT, CostLedger, LedgerRange
from app.research.my_tasks import CLAIMS_PER_CALL_MAX, MyTasks, TaskClaims
from app.research.open_work import TASK_KEY_MAX_CHARS
from app.research.review_switch import CONTRIBUTION
from app.research.stewardship import MyCrafts, StewardPackage, Stewardship
from app.research.trust_tiers import TierUpdate, TrustStanding, TrustStandings
from app.services import (
    contribution_queue,
    contribution_queue_tasks,
    contribution_queue_tickets,
    cost_ledger,
    stewardship,
    task_reservations,
    trust_tiers,
)
from app.services.contribution_queue import QueuedFact
from app.services.own_proposals import require_terms

router = APIRouter(prefix="/knowledge", tags=["knowledge"])
contributor = require(Capability.PROPOSE_KNOWLEDGE)
tier_keeper = require(Capability.REVIEW_CONTRIBUTIONS)
ledger_reader = require(Capability.VIEW_USAGE)

TaskKey = Annotated[str, Field(min_length=1, max_length=TASK_KEY_MAX_CHARS)]


class TaskKeysBody(ContractModel):
    task_keys: list[TaskKey] = Field(min_length=1, max_length=CLAIMS_PER_CALL_MAX)


@router.post("/proposals/facts")
async def propose_facts(
    body: FactBatchBody, user: User = Depends(contributor), session: AsyncSession = Depends(get_session)
) -> ProposalBatch:
    try:
        await require_terms(session, user)
    except Refused as refused:
        raise HTTPException(status.HTTP_403_FORBIDDEN, refused.message) from None
    facts = [
        QueuedFact(index=index, proposal=item.proposal, key=item.idempotency_key)
        for index, item in enumerate(body.facts)
    ]
    return await _written(
        session, contribution_queue.enqueue_facts(session, user, facts, origin=CONTRIBUTION, now=_now())
    )


@router.get("/proposals")
async def my_proposals(
    limit: int = Query(default=RECENT_PROPOSALS_MAX, ge=1, le=RECENT_PROPOSALS_MAX),
    user: User = Depends(contributor),
    session: AsyncSession = Depends(get_session),
) -> ProposalTickets:
    return await contribution_queue_tickets.recent_tickets(session, user.id, limit=limit)


@router.get("/proposals/{proposal_id}")
async def get_proposal(
    proposal_id: uuid.UUID, user: User = Depends(contributor), session: AsyncSession = Depends(get_session)
) -> ProposalTicket:
    return await _read(contribution_queue_tickets.own_ticket(session, user, proposal_id))


@router.get("/open-work/mine")
async def my_tasks(
    user: User = Depends(contributor), session: AsyncSession = Depends(get_session)
) -> MyTasks:
    return await contribution_queue_tasks.my_tasks(session, user, site=_site(), now=_now())


@router.post("/open-work/claims")
async def claim_tasks(
    body: TaskKeysBody, user: User = Depends(contributor), session: AsyncSession = Depends(get_session)
) -> TaskClaims:
    return await _written(
        session,
        task_reservations.claim_tasks(session, user.id, list(body.task_keys), site=_site(), now=_now()),
    )


@router.get("/stewardship")
async def my_crafts(
    user: User = Depends(contributor), session: AsyncSession = Depends(get_session)
) -> MyCrafts:
    return await _written(session, stewardship.my_crafts(session, user, site=_site(), now=_now()))


@router.put("/stewardship/{slug}")
async def adopt_craft(
    slug: str, user: User = Depends(contributor), session: AsyncSession = Depends(get_session)
) -> StewardPackage:
    return await _written(session, stewardship.adopt_craft(session, user, slug, site=_site(), now=_now()))


@router.delete("/stewardship/{slug}")
async def drop_craft(
    slug: str, user: User = Depends(contributor), session: AsyncSession = Depends(get_session)
) -> Stewardship:
    return await _written(session, stewardship.drop_craft(session, user, slug, now=_now()))


@router.get("/trust-tiers")
async def trust_standings(
    limit: int = Query(default=100, ge=1, le=trust_tiers.STANDINGS_LIMIT_MAX),
    _: User = Depends(tier_keeper),
    session: AsyncSession = Depends(get_session),
) -> TrustStandings:
    return await trust_tiers.trust_standings(session, limit=limit)


@router.get("/trust-tiers/{user_id}")
async def trust_standing(
    user_id: uuid.UUID, _: User = Depends(tier_keeper), session: AsyncSession = Depends(get_session)
) -> TrustStanding:
    return await _read(trust_tiers.account_standing(session, user_id))


@router.put("/trust-tiers/{user_id}")
async def set_trust_tier(
    user_id: uuid.UUID,
    body: TierUpdate,
    actor: User = Depends(tier_keeper),
    session: AsyncSession = Depends(get_session),
) -> TrustStanding:
    return await _written(session, trust_tiers.set_tier(session, actor, user_id, body, now=_now()))


@router.get("/contribution-costs")
async def contribution_costs(
    day_from: date | None = Query(default=None, alias="from"),
    day_to: date | None = Query(default=None, alias="to"),
    _: User = Depends(ledger_reader),
    session: AsyncSession = Depends(get_session),
) -> CostLedger:
    today = _now().astimezone(INDIA_TZ).date()
    last = day_to or today
    first = day_from or last - timedelta(days=LEDGER_DAYS_DEFAULT - 1)
    try:
        span = LedgerRange(day_from=first, day_to=last)
    except ValueError as invalid:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(invalid)) from None
    return await cost_ledger.cost_ledger(session, span)


async def _read[Kept](found: Awaitable[Kept]) -> Kept:
    try:
        return await found
    except InvalidInput as invalid:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(invalid)) from None


async def _written[Kept](session: AsyncSession, change: Awaitable[Kept]) -> Kept:
    try:
        kept = await change
    except InvalidInput as invalid:
        await session.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(invalid)) from None
    except Refused as refused:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, refused.message) from None
    await session.commit()
    return kept


def _now() -> datetime:
    return datetime.now(UTC)


def _site() -> str:
    return get_settings().public_web_url.rstrip("/")
