from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from datetime import datetime

from sqlalchemy import func, select, union
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.core.roles import PROFESSOR, has_rank
from app.models import Claim, TrustTierOverride, User
from app.research.trust_tiers import (
    PROVEN,
    REVIEW_SAMPLE_PERCENT,
    TIER_FACTS_PER_HOUR,
    TIER_TASKS_HELD,
    TierOverrideView,
    TierRecord,
    TierUpdate,
    TrustStanding,
    TrustStandings,
    earned_tier,
)

from . import audit
from .proposal_writes import PROPOSAL_CLAIM_ORIGIN

__all__ = [
    "ACCEPTED_STATUSES",
    "REFUSED_STATUSES",
    "STANDINGS_LIMIT_MAX",
    "TIER_SET_ACTION",
    "WAITING_STATUSES",
    "account_standing",
    "set_tier",
    "standing_of",
    "tier_records",
    "trust_standings",
]

ACCEPTED_STATUSES = ("APPROVED", "IN_REVIEW", "PROPOSED")
REFUSED_STATUSES = ("REJECTED", "RETRACTED")
WAITING_STATUSES = ("DRAFT",)
STANDINGS_LIMIT_MAX = 200
TIER_SET_ACTION = "knowledge.trust_tier_set"
NO_ACCOUNT = "No account has the id {user_id}."
EVERY_ITEM = 100


async def tier_records(session: AsyncSession, user_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, TierRecord]:
    if not user_ids:
        return {}
    rows = await session.execute(
        select(Claim.createdById, Claim.status, func.count())
        .where(Claim.createdById.in_(list(user_ids)), Claim.origin == PROPOSAL_CLAIM_ORIGIN)
        .group_by(Claim.createdById, Claim.status)
    )
    counted: dict[uuid.UUID, dict[str, int]] = {user_id: {} for user_id in user_ids}
    for user_id, status, count in rows.all():
        counted[user_id][str(status)] = int(count)
    return {user_id: _record(by_status) for user_id, by_status in counted.items()}


async def account_standing(session: AsyncSession, user_id: uuid.UUID) -> TrustStanding:
    user = await session.get(User, user_id)
    if user is None:
        raise InvalidInput(NO_ACCOUNT.format(user_id=user_id))
    records = await tier_records(session, [user_id])
    return standing_of(user, records[user_id], await session.get(TrustTierOverride, user_id))


def standing_of(user: User, record: TierRecord, override: TrustTierOverride | None) -> TrustStanding:
    earned = earned_tier(record)
    tier = override.tier if override is not None else earned
    reviews = has_rank(user.role, PROFESSOR)
    allowance = PROVEN if reviews else tier
    return TrustStanding(
        user_id=user.id,
        name=user.name,
        role=str(user.role),
        tier=tier,
        earned=earned,
        accepted=record.accepted,
        refused=record.refused,
        waiting=record.waiting,
        tasks_held_max=TIER_TASKS_HELD[allowance],
        facts_per_hour=TIER_FACTS_PER_HOUR[allowance],
        review_sample_percent=0 if reviews else REVIEW_SAMPLE_PERCENT if tier == PROVEN else EVERY_ITEM,
        override=_override_view(override),
    )


async def trust_standings(session: AsyncSession, *, limit: int) -> TrustStandings:
    contributors = select(Claim.createdById.label("user_id")).where(
        Claim.origin == PROPOSAL_CLAIM_ORIGIN, Claim.createdById.is_not(None)
    )
    held = select(TrustTierOverride.userId.label("user_id"))
    ids = list((await session.scalars(select(union(contributors, held).subquery().c.user_id))).all())
    users = {user.id: user for user in await session.scalars(select(User).where(User.id.in_(ids)))}
    records = await tier_records(session, list(users))
    overrides = await _overrides(session, list(users))
    accounts = [standing_of(user, records[user.id], overrides.get(user.id)) for user in users.values()]
    ranked = sorted(accounts, key=lambda item: (-item.accepted, item.refused, str(item.user_id)))
    return TrustStandings(accounts=ranked[: min(limit, STANDINGS_LIMIT_MAX)])


async def set_tier(
    session: AsyncSession, actor: User, user_id: uuid.UUID, update: TierUpdate, *, now: datetime
) -> TrustStanding:
    if await session.get(User, user_id) is None:
        raise InvalidInput(NO_ACCOUNT.format(user_id=user_id))
    current = await session.get(TrustTierOverride, user_id)
    if update.tier is None and current is not None:
        await session.delete(current)
    elif update.tier is not None and current is None:
        session.add(
            TrustTierOverride(userId=user_id, tier=update.tier, note=update.note, setById=actor.id, setAt=now)
        )
    elif update.tier is not None and current is not None:
        current.tier, current.note, current.setById, current.setAt = update.tier, update.note, actor.id, now
    await session.flush()
    await audit.record(
        session,
        action=TIER_SET_ACTION,
        actor=actor,
        target_type="User",
        target_id=user_id,
        detail={"tier": update.tier, "note": update.note},
    )
    await session.flush()
    return await account_standing(session, user_id)


async def _overrides(
    session: AsyncSession, user_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, TrustTierOverride]:
    if not user_ids:
        return {}
    rows = await session.scalars(
        select(TrustTierOverride).where(TrustTierOverride.userId.in_(list(user_ids)))
    )
    return {row.userId: row for row in rows}


def _record(by_status: Mapping[str, int]) -> TierRecord:
    return TierRecord(
        accepted=sum(by_status.get(status, 0) for status in ACCEPTED_STATUSES),
        refused=sum(by_status.get(status, 0) for status in REFUSED_STATUSES),
        waiting=sum(by_status.get(status, 0) for status in WAITING_STATUSES),
    )


def _override_view(override: TrustTierOverride | None) -> TierOverrideView | None:
    if override is None:
        return None
    return TierOverrideView(
        tier=override.tier, note=override.note, set_at=override.setAt, set_by=override.setById
    )
