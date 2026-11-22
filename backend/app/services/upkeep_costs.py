from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Answer, UsageEvent

__all__ = ["LATE_COST_WINDOW", "REQUEST_SPAN", "LateCostsReport", "settle_late_costs"]

LATE_COST_WINDOW = timedelta(days=7)
REQUEST_SPAN = timedelta(hours=1)


@dataclass
class LateCostsReport:
    updated: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {"answersUpdated": self.updated}


async def settle_late_costs(session: AsyncSession, *, now: datetime) -> LateCostsReport:
    since = now - LATE_COST_WINDOW
    settled = (
        select(UsageEvent.requestId.label("request_id"), func.sum(UsageEvent.costUsd).label("cost"))
        .where(UsageEvent.requestId.is_not(None), UsageEvent.createdAt >= since - REQUEST_SPAN)
        .group_by(UsageEvent.requestId)
        .subquery()
    )
    result = await session.execute(
        update(Answer)
        .where(
            Answer.requestId == settled.c.request_id,
            Answer.createdAt >= since,
            Answer.costUsd != settled.c.cost,
        )
        .values(costUsd=settled.c.cost)
        .execution_options(synchronize_session=False)
    )
    await session.commit()
    return LateCostsReport(updated=result.rowcount or 0)
