from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from .app_settings import get_value, set_value
from .reader_facts import HIDDEN_REASONS, CraftHidden, craft_hidden

__all__ = [
    "CRAFTS_LISTED_MAX",
    "HIDDEN_FACTS_SETTING",
    "HiddenReport",
    "count_hidden_facts",
    "last_hidden_facts",
]

HIDDEN_FACTS_SETTING = "upkeep.hiddenFacts"
CRAFTS_LISTED_MAX = 200


@dataclass
class HiddenReport:
    crafts: list[CraftHidden] = field(default_factory=list)
    counted_at: datetime | None = None

    @property
    def unexplained(self) -> int:
        return sum(len(craft.unexplained) for craft in self.crafts)

    def by_reason(self) -> dict[str, int]:
        totals: Counter[str] = Counter(dict.fromkeys(HIDDEN_REASONS, 0))
        for craft in self.crafts:
            totals.update(craft.hidden)
        return dict(totals)

    def as_dict(self) -> dict[str, Any]:
        unexplained = [craft.slug for craft in self.crafts if craft.unexplained]
        return {
            "countedAt": self.counted_at.isoformat() if self.counted_at else None,
            "crafts": len(self.crafts),
            "byReason": self.by_reason(),
            "unexplained": self.unexplained,
            "craftsUnexplained": unexplained,
            "perCraft": [craft.as_dict() for craft in self.crafts[:CRAFTS_LISTED_MAX]],
        }


async def count_hidden_facts(session: AsyncSession, *, now: datetime) -> HiddenReport:
    report = HiddenReport(crafts=await craft_hidden(session), counted_at=now)
    await set_value(session, HIDDEN_FACTS_SETTING, report.as_dict())
    await session.commit()
    return report


async def last_hidden_facts(session: AsyncSession) -> dict[str, Any] | None:
    stored = await get_value(session, HIDDEN_FACTS_SETTING)
    return stored if isinstance(stored, dict) else None
