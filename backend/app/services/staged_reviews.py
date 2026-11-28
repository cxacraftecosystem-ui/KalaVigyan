from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, time

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import INDIA_TZ
from app.core.errors import AppError, InvalidInput
from app.core.roles import Capability, can
from app.models import ArtisanContribution, Claim, StagedReview, StagedReviewItem, User
from app.research.review_labels import cut_label, queue_label
from app.research.staged_reviews import (
    OPEN,
    SOURCES,
    SOURCES_DIFFER,
    StagedDecision,
    acts_on_published,
    batch_expiry,
    day_allowance_problem,
    stored_decision,
)

from .oauth_bearer import McpCaller
from .page_proposal_reviews import page_label
from .review_queue import QueueAdapters, open_review_item
from .review_queue_decisions import ItemRef
from .review_queue_errors import NotYourQueue, refusal_of
from .source_corrections import source_label
from .staged_published import published_before, published_label
from .staged_review_apply import dry_run
from .testimony_views import Turns

__all__ = [
    "ASKED_ALREADY",
    "Staged",
    "StagedRefusal",
    "request_problem",
    "stage_decisions",
    "stage_request",
    "staged_today",
]

NOT_AN_ADMIN = "Staging review decisions is for Admins and Master Admins."
TWICE = "This item is already decided earlier in the same call."
NOT_WAITING = "No {kind} item with this id is in the review queue you review."
NOT_PUBLISHED = "No published {kind} item has this id; review_queue with published lists them by page."
NO_SOURCE = "No source has this id."
NO_FACT = "No fact has this id."
NO_TRANSCRIPTS = "Testimony is reviewed on the site, not over MCP."
ASKED_ALREADY = "This change already waits for an Admin's confirmation on the Review page."


@dataclass(frozen=True)
class StagedRefusal:
    index: int
    kind: str
    id: uuid.UUID
    reason: str


@dataclass(frozen=True)
class _Checked:
    decision: StagedDecision
    label: str | None = None
    problem: str | None = None


@dataclass
class Staged:
    batch: StagedReview | None = None
    items: list[StagedReviewItem] = field(default_factory=list)
    refused: list[StagedRefusal] = field(default_factory=list)
    today: int = 0


async def stage_decisions(
    session: AsyncSession, asked: Sequence[StagedDecision], caller: McpCaller, *, now: datetime
) -> Staged:
    proposer = caller.user
    if not can(proposer, Capability.REVIEW_CONTRIBUTIONS):
        raise NotYourQueue(NOT_AN_ADMIN)
    staged = Staged(today=await staged_today(session, proposer, now=now))
    kept: list[tuple[StagedDecision, str]] = []
    seen: set[tuple[object, ...]] = set()
    for index, decision in enumerate(asked):
        checked = await _checked(session, decision, proposer, seen=seen, now=now)
        if checked.problem is not None or checked.label is None:
            reason = checked.problem or NOT_WAITING
            staged.refused.append(StagedRefusal(index, decision.kind, decision.id, reason))
            continue
        seen.add(_target(decision))
        kept.append((checked.decision, checked.label))
    over = day_allowance_problem(staged.today, len(kept))
    if over is not None:
        raise InvalidInput(over)
    if kept:
        staged.batch, staged.items = await _stored(session, kept, _batch(caller, now=now))
        staged.today += len(kept)
    return staged


async def stage_request(
    session: AsyncSession, decision: StagedDecision, proposer: User, *, client_name: str, now: datetime
) -> StagedReviewItem:
    problem = await request_problem(session, decision, now=now)
    if problem is not None:
        raise InvalidInput(problem)
    label = str(await published_label(session, decision))
    batch = StagedReview(
        proposerId=proposer.id, clientName=client_name, createdAt=now, expiresAt=batch_expiry(now)
    )
    _, (item,) = await _stored(session, [(decision, label)], batch)
    return item


async def request_problem(session: AsyncSession, decision: StagedDecision, *, now: datetime) -> str | None:
    if await published_label(session, decision) is None:
        return _missing(decision)
    if await _waiting(session, decision, now=now):
        return ASKED_ALREADY
    return None


async def staged_today(session: AsyncSession, proposer: User, *, now: datetime) -> int:
    midnight = datetime.combine(now.astimezone(INDIA_TZ).date(), time(), tzinfo=INDIA_TZ)
    counted = await session.scalar(
        select(func.count(StagedReviewItem.id))
        .join(StagedReview, StagedReview.id == StagedReviewItem.batchId)
        .where(StagedReview.proposerId == proposer.id, StagedReview.createdAt >= midnight)
    )
    return int(counted or 0)


async def _checked(
    session: AsyncSession,
    decision: StagedDecision,
    proposer: User,
    *,
    seen: set[tuple[object, ...]],
    now: datetime,
) -> _Checked:
    if _target(decision) in seen:
        return _Checked(decision, problem=TWICE)
    try:
        filled = await published_before(session, decision)
        label = None if filled is None else await _label(session, filled, proposer, now=now)
    except (AppError, ValidationError) as refused:
        return _Checked(decision, problem=refusal_of(refused))
    if filled is None or label is None:
        return _Checked(decision, problem=_missing(decision))
    return _Checked(filled, label, await dry_run(session, filled, proposer, now=now))


async def _label(
    session: AsyncSession, decision: StagedDecision, proposer: User, *, now: datetime
) -> str | None:
    if acts_on_published(decision.action):
        return await published_label(session, decision)
    if decision.kind == SOURCES:
        title = await source_label(session, decision.id)
        return None if title is None else cut_label(f"Source: {title}")
    if decision.kind == SOURCES_DIFFER:
        text = await session.scalar(select(Claim.text).where(Claim.id == decision.id))
        return None if text is None else cut_label(f"Sources differ: {text}")
    if decision.page is not None:
        return await page_label(session, decision.id, decision.page)
    adapters = QueueAdapters(objects=None, turns_of=_no_transcripts)
    item = await open_review_item(
        session, proposer, ItemRef(decision.kind, decision.id), adapters=adapters, now=now
    )
    return None if item is None else queue_label(item)


def _target(decision: StagedDecision) -> tuple[object, ...]:
    if decision.page is None:
        return (decision.kind, decision.id)
    return (decision.kind, decision.id, decision.page.scope, decision.page.chapter, decision.page.label)


def _missing(decision: StagedDecision) -> str:
    if acts_on_published(decision.action):
        return NOT_PUBLISHED.format(kind=decision.kind.lower())
    if decision.kind == SOURCES:
        return NO_SOURCE
    if decision.kind == SOURCES_DIFFER:
        return NO_FACT
    return NOT_WAITING.format(kind=decision.kind.lower())


async def _waiting(session: AsyncSession, decision: StagedDecision, *, now: datetime) -> bool:
    found = await session.scalar(
        select(StagedReviewItem.id)
        .join(StagedReview, StagedReview.id == StagedReviewItem.batchId)
        .where(
            StagedReviewItem.kind == decision.kind,
            StagedReviewItem.itemId == decision.id,
            StagedReviewItem.action == decision.action,
            StagedReview.status == OPEN,
            StagedReview.expiresAt > now,
        )
        .limit(1)
    )
    return found is not None


def _batch(caller: McpCaller, *, now: datetime) -> StagedReview:
    return StagedReview(
        proposerId=caller.user.id,
        grantId=caller.grant_id,
        tokenId=caller.token_id,
        clientName=caller.client_name,
        createdAt=now,
        expiresAt=batch_expiry(now),
    )


async def _stored(
    session: AsyncSession, kept: list[tuple[StagedDecision, str]], batch: StagedReview
) -> tuple[StagedReview, list[StagedReviewItem]]:
    session.add(batch)
    await session.flush()
    items = [
        StagedReviewItem(
            batchId=batch.id,
            position=position,
            kind=decision.kind,
            itemId=decision.id,
            action=decision.action,
            decision=stored_decision(decision),
            label=label,
        )
        for position, (decision, label) in enumerate(kept)
    ]
    session.add_all(items)
    await session.flush()
    return batch, items


async def _no_transcripts(_: ArtisanContribution) -> Turns:
    raise InvalidInput(NO_TRANSCRIPTS)
