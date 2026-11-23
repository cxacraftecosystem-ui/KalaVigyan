from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import datetime, time

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import INDIA_TZ
from app.core.errors import InvalidInput
from app.core.roles import Capability, can
from app.models import ArtisanContribution, Claim, StagedReview, StagedReviewItem, User
from app.research.review_labels import cut_label, queue_label
from app.research.staged_reviews import (
    SOURCES,
    SOURCES_DIFFER,
    StagedDecision,
    batch_expiry,
    day_allowance_problem,
)

from .oauth_bearer import McpCaller
from .review_queue import QueueAdapters, open_review_item
from .review_queue_decisions import ItemRef
from .review_queue_errors import NotYourQueue
from .source_corrections import source_label
from .staged_review_apply import dry_run
from .testimony_views import Turns

__all__ = ["Staged", "StagedRefusal", "stage_decisions", "staged_today"]

NOT_AN_ADMIN = "Staging review decisions is for Admins and Master Admins."
TWICE = "This item is already decided earlier in the same call."
NOT_WAITING = "No {kind} item with this id is in the review queue you review."
NO_SOURCE = "No source has this id."
NO_FACT = "No fact has this id."
NO_TRANSCRIPTS = "Testimony is reviewed on the site, not over MCP."


@dataclass(frozen=True)
class StagedRefusal:
    index: int
    kind: str
    id: uuid.UUID
    reason: str


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
    seen: set[tuple[str, uuid.UUID]] = set()
    for index, decision in enumerate(asked):
        label, problem = await _checked(session, decision, proposer, seen=seen, now=now)
        if problem is not None or label is None:
            staged.refused.append(StagedRefusal(index, decision.kind, decision.id, problem or NOT_WAITING))
            continue
        seen.add((decision.kind, decision.id))
        kept.append((decision, label))
    over = day_allowance_problem(staged.today, len(kept))
    if over is not None:
        raise InvalidInput(over)
    if kept:
        staged.batch, staged.items = await _stored(session, kept, caller, now=now)
        staged.today += len(kept)
    return staged


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
    seen: set[tuple[str, uuid.UUID]],
    now: datetime,
) -> tuple[str | None, str | None]:
    if (decision.kind, decision.id) in seen:
        return None, TWICE
    label = await _label(session, decision, proposer, now=now)
    if label is None:
        return None, _missing(decision)
    return label, await dry_run(session, decision, proposer, now=now)


async def _label(
    session: AsyncSession, decision: StagedDecision, proposer: User, *, now: datetime
) -> str | None:
    if decision.kind == SOURCES:
        title = await source_label(session, decision.id)
        return None if title is None else cut_label(f"Source: {title}")
    if decision.kind == SOURCES_DIFFER:
        text = await session.scalar(select(Claim.text).where(Claim.id == decision.id))
        return None if text is None else cut_label(f"Sources differ: {text}")
    adapters = QueueAdapters(objects=None, turns_of=_no_transcripts)
    item = await open_review_item(
        session, proposer, ItemRef(decision.kind, decision.id), adapters=adapters, now=now
    )
    return None if item is None else queue_label(item)


def _missing(decision: StagedDecision) -> str:
    if decision.kind == SOURCES:
        return NO_SOURCE
    if decision.kind == SOURCES_DIFFER:
        return NO_FACT
    return NOT_WAITING.format(kind=decision.kind.lower())


async def _stored(
    session: AsyncSession, kept: list[tuple[StagedDecision, str]], caller: McpCaller, *, now: datetime
) -> tuple[StagedReview, list[StagedReviewItem]]:
    batch = StagedReview(
        proposerId=caller.user.id,
        grantId=caller.grant_id,
        tokenId=caller.token_id,
        clientName=caller.client_name,
        createdAt=now,
        expiresAt=batch_expiry(now),
    )
    session.add(batch)
    await session.flush()
    items = [
        StagedReviewItem(
            batchId=batch.id,
            position=position,
            kind=decision.kind,
            itemId=decision.id,
            action=decision.action,
            decision=decision.model_dump(mode="json", exclude_none=True),
            label=label,
        )
        for position, (decision, label) in enumerate(kept)
    ]
    session.add_all(items)
    await session.flush()
    return batch, items


async def _no_transcripts(_: ArtisanContribution) -> Turns:
    raise InvalidInput(NO_TRANSCRIPTS)
