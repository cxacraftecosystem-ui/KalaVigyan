from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from sqlalchemy import String, func, literal, update
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Answer

__all__ = [
    "ADDED",
    "BUILDS_KEY",
    "FAILED",
    "NOTHING",
    "TIMED_OUT",
    "BuildRecord",
    "BuilderOutcome",
    "answer_build_record",
    "with_builds",
]

logger = logging.getLogger(__name__)

BUILDS_KEY = "builds"
ADDED = "ADDED"
NOTHING = "NOTHING"
TIMED_OUT = "TIMED_OUT"
FAILED = "FAILED"
SECONDS_PLACES = 1


@dataclass(frozen=True)
class BuilderOutcome:
    kind: str
    outcome: str
    blocks: int
    seconds: float

    def plain(self, section_id: str) -> dict[str, Any]:
        return {
            "sectionId": section_id,
            "kind": self.kind,
            "outcome": self.outcome,
            "blocks": self.blocks,
            "seconds": round(self.seconds, SECONDS_PLACES),
        }


class BuildRecord(Protocol):
    async def __call__(
        self, answer_id: uuid.UUID, section_id: str, outcomes: Sequence[BuilderOutcome]
    ) -> None: ...


def answer_build_record(sessions: async_sessionmaker[AsyncSession]) -> BuildRecord:
    async def record(answer_id: uuid.UUID, section_id: str, outcomes: Sequence[BuilderOutcome]) -> None:
        notes = [outcome.plain(section_id) for outcome in outcomes]
        try:
            async with sessions() as session:
                await session.execute(
                    update(Answer).where(Answer.id == answer_id).values(plan=with_builds(notes))
                )
                await session.commit()
        except SQLAlchemyError:
            logger.warning(
                "the builders of section %s of answer %s were not recorded",
                section_id,
                answer_id,
                exc_info=True,
            )

    return record


def with_builds(notes: Sequence[dict[str, Any]]) -> Any:
    plan = func.coalesce(Answer.plan, literal({}, JSONB))
    kept = func.coalesce(Answer.plan[BUILDS_KEY], literal([], JSONB))
    builds = func.jsonb_build_object(literal(BUILDS_KEY, String), kept.op("||")(literal(list(notes), JSONB)))
    return plan.op("||")(builds)
