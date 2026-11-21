from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import AnswerGap
from app.research.embedding import TextEmbedder

from .answer_gap_checks import answered_gaps, end_closed_reservations, recount_gaps
from .answer_gap_groups import Grouped, group_questions
from .open_work_gaps import OPEN_GAP

__all__ = ["AnswerGapsReport", "refresh_answer_gaps"]


@dataclass
class AnswerGapsReport:
    grouped: Grouped = field(default_factory=Grouped)
    answered: int = 0
    lapsed: int = 0
    open: int = 0
    reservations_closed: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "questions": self.grouped.candidates,
            "dropped": self.grouped.dropped,
            "embedded": self.grouped.embedded,
            "embeddingError": self.grouped.embedding_error,
            "joined": self.grouped.joined,
            "opened": self.grouped.opened,
            "answered": self.answered,
            "lapsed": self.lapsed,
            "open": self.open,
            "reservationsClosed": self.reservations_closed,
        }


async def refresh_answer_gaps(
    session: AsyncSession, embed: TextEmbedder | None, *, now: datetime
) -> AnswerGapsReport:
    report = AnswerGapsReport(grouped=await group_questions(session, embed, now=now))
    report.lapsed = len(await recount_gaps(session, now=now))
    report.answered = len(await answered_gaps(session, now=now))
    report.reservations_closed = len(await end_closed_reservations(session, now=now))
    still_open = select(func.count()).select_from(AnswerGap).where(AnswerGap.state == OPEN_GAP)
    report.open = int((await session.execute(still_open)).scalar_one())
    return report
