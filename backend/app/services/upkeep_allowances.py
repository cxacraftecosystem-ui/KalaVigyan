from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.allowances import delete_old_buckets

__all__ = ["AllowancesReport", "sweep_allowances"]


@dataclass
class AllowancesReport:
    deleted: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {"bucketsDeleted": self.deleted}


async def sweep_allowances(session: AsyncSession, *, now: datetime) -> AllowancesReport:
    report = AllowancesReport(deleted=await delete_old_buckets(session, now=now))
    await session.commit()
    return report
