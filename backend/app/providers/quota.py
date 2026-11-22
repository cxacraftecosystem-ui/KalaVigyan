from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import daily_allowances
from app.core.errors import InvalidInput
from app.models import QuotaLedger
from app.models.enums import QUOTA_RESOURCES

from .budget import day_start

__all__ = [
    "LedgerEntry",
    "next_day_start",
    "record_units",
    "remaining_today",
    "seconds_until_next_day",
    "used_today",
]


@dataclass(frozen=True)
class LedgerEntry:
    user_id: uuid.UUID | None
    resource: str
    units: int
    key: str
    ref_type: str | None = None
    ref_id: str | None = None


async def used_today(session: AsyncSession, *, user_id: uuid.UUID, resource: str, now: datetime) -> int:
    _known(resource)
    await daily_allowances.refresh_if_stale(session)
    total = await session.scalar(
        select(func.coalesce(func.sum(QuotaLedger.units), 0)).where(
            QuotaLedger.userId == user_id,
            QuotaLedger.resource == resource,
            QuotaLedger.createdAt >= day_start(now),
        )
    )
    return max(0, math.ceil(Decimal(total or 0)))


def remaining_today(user: Any, resource: str, used: int) -> int | None:
    _known(resource)
    allowance = daily_allowances.daily_allowance(user, resource)
    if allowance is None:
        return None
    return max(0, int(allowance) - used)


async def record_units(session: AsyncSession, entry: LedgerEntry) -> bool:
    _known(entry.resource)
    inserted = await session.execute(
        insert(QuotaLedger)
        .values(
            userId=entry.user_id,
            resource=entry.resource,
            units=entry.units,
            refType=entry.ref_type,
            refId=entry.ref_id,
            idempotencyKey=entry.key,
        )
        .on_conflict_do_nothing(index_elements=[QuotaLedger.idempotencyKey])
        .returning(QuotaLedger.id)
    )
    return inserted.scalar_one_or_none() is not None


def next_day_start(now: datetime) -> datetime:
    return day_start(now) + timedelta(days=1)


def seconds_until_next_day(now: datetime) -> int:
    return max(1, math.ceil((next_day_start(now) - now).total_seconds()))


def _known(resource: str) -> None:
    if resource not in QUOTA_RESOURCES:
        raise InvalidInput(f"Unknown quota resource {resource!r}")
