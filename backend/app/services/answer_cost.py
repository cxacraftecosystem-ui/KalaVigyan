from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import current_request_id
from app.models import UsageEvent

__all__ = ["COST_PLACES", "answer_measures", "latency_ms", "request_cost"]

logger = logging.getLogger(__name__)

COST_PLACES = Decimal("0.000001")
MILLISECONDS = 1000


def latency_ms(asked_at: datetime, finished_at: datetime) -> int:
    if finished_at < asked_at:
        raise ValueError(f"an answer finished at {finished_at} before it was asked at {asked_at}")
    return round((finished_at - asked_at).total_seconds() * MILLISECONDS)


async def request_cost(session: AsyncSession, request_id: str) -> Decimal:
    total = await session.scalar(
        select(func.coalesce(func.sum(UsageEvent.costUsd), 0)).where(UsageEvent.requestId == request_id)
    )
    return Decimal(total or 0).quantize(COST_PLACES)


async def answer_measures(
    session: AsyncSession, *, asked_at: datetime, finished_at: datetime
) -> dict[str, Any]:
    measures: dict[str, Any] = {"latencyMs": latency_ms(asked_at, finished_at)}
    request_id = current_request_id()
    if request_id is None:
        logger.warning("an answer finished outside a request id, so its cost is not recorded")
        return measures
    return measures | {"costUsd": await request_cost(session, request_id)}
