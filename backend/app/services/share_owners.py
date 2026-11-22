from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Answer, LessonPack

from . import audit
from .shared_files import FileDeleter, drop_stopped_share_files

__all__ = [
    "SHARES_WITHDRAWN",
    "WithdrawnShares",
    "withdraw_lesson_shares",
    "withdraw_shares",
]

SHARES_WITHDRAWN = "shares.withdrawn"


@dataclass(frozen=True, slots=True)
class WithdrawnShares:
    answers: int
    lessons: int

    def audit_detail(self, cause: str) -> dict[str, Any]:
        return {"cause": cause, "answers": self.answers, "lessons": self.lessons}

    @property
    def total(self) -> int:
        return self.answers + self.lessons


async def withdraw_shares(
    session: AsyncSession, owner_id: uuid.UUID, *, actor: Any, cause: str, objects: FileDeleter | None
) -> WithdrawnShares:
    withdrawn = WithdrawnShares(
        answers=await _withdraw(session, Answer, owner_id),
        lessons=await _withdraw(session, LessonPack, owner_id),
    )
    await _settle(session, owner_id, withdrawn, actor=actor, cause=cause, objects=objects)
    return withdrawn


async def withdraw_lesson_shares(
    session: AsyncSession, owner_id: uuid.UUID, *, actor: Any, cause: str, objects: FileDeleter | None
) -> WithdrawnShares:
    withdrawn = WithdrawnShares(answers=0, lessons=await _withdraw(session, LessonPack, owner_id))
    await _settle(session, owner_id, withdrawn, actor=actor, cause=cause, objects=objects)
    return withdrawn


async def _withdraw(session: AsyncSession, table: Any, owner_id: uuid.UUID) -> int:
    found = await session.execute(
        update(table)
        .where(table.userId == owner_id, table.shareToken.is_not(None))
        .values(shareToken=None, sharedAt=None)
        .returning(table.id)
        .execution_options(synchronize_session=False)
    )
    return len(found.all())


async def _settle(
    session: AsyncSession,
    owner_id: uuid.UUID,
    withdrawn: WithdrawnShares,
    *,
    actor: Any,
    cause: str,
    objects: FileDeleter | None,
) -> None:
    if withdrawn.total == 0:
        return
    await drop_stopped_share_files(session, objects)
    await audit.record(
        session,
        action=SHARES_WITHDRAWN,
        actor=actor,
        target_type="User",
        target_id=owner_id,
        detail=withdrawn.audit_detail(cause),
    )
