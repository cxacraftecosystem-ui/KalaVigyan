from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Answer, User
from app.providers.quota import LedgerEntry, record_units, remaining_today, used_today
from app.research.explainer import Explainer
from app.services.explainer_payload import stored_explainer
from app.services.field_voices_readback import current_field_voices

from .listen_ask import ListenHold
from .seconds import VOICE_SECONDS

__all__ = ["SqlListenStore"]


class SqlListenStore:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def explainer(self, answer_id: uuid.UUID, user_id: uuid.UUID) -> Explainer | None:
        async with self._sessions() as session:
            payload = await session.scalar(
                select(Answer.payload).where(Answer.id == answer_id, Answer.userId == user_id)
            )
            explainer = stored_explainer(answer_id, payload)
            return await current_field_voices(session, explainer) if explainer is not None else None

    async def hold(self, entry: LedgerEntry, now: datetime) -> ListenHold:
        if entry.user_id is None:
            return ListenHold(held=0, remaining_after=0, refused=True)
        async with self._sessions() as session:
            role = await session.scalar(select(User.role).where(User.id == entry.user_id).with_for_update())
            if role is None:
                return ListenHold(held=0, remaining_after=0, refused=True)
            used = await used_today(session, user_id=entry.user_id, resource=VOICE_SECONDS, now=now)
            remaining = remaining_today(role, VOICE_SECONDS, used)
            if remaining is not None and remaining < entry.units:
                return ListenHold(held=0, remaining_after=remaining, refused=True)
            await record_units(session, entry)
            await session.commit()
        after = None if remaining is None else remaining - entry.units
        return ListenHold(held=entry.units, remaining_after=after)

    async def record(self, entry: LedgerEntry) -> None:
        async with self._sessions() as session:
            await record_units(session, entry)
            await session.commit()
