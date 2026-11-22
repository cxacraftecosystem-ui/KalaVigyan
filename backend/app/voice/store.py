from __future__ import annotations

import uuid
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import DateTime, Interval, and_, case, func, literal, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import (
    Answer,
    ConsentRecord,
    Conversation,
    Craft,
    Process,
    ProcessStage,
    QuotaLedger,
    User,
    VoiceSession,
)
from app.providers.quota import LedgerEntry, record_units, remaining_today, used_today
from app.research.crafts import CraftRef
from app.research.retrieval import EVERY_CHUNK_ACLS
from app.schemas.voice import MAX_TURNS, TRANSCRIPT_RETENTION_DAYS
from app.services import knowledge_view
from app.services.answer_events import cited_claims

from .pack import VoicePack
from .records import AnswerRecord, SessionRecord, TurnClaim, TurnHold, TurnSave
from .seconds import AGENT_OCCUPANCY_SECONDS, VOICE_SECONDS, capped_seconds

__all__ = ["VOICE_ANSWER_QUESTION", "VOICE_TIERS", "SqlVoiceStore", "answer_row", "session_row"]

VOICE_ANSWER_QUESTION = "Voice turn"
VOICE_TIERS = ["T1"]
RETENTION = timedelta(days=TRANSCRIPT_RETENTION_DAYS)
LIVE_INDEX = "VoiceSession_one_live_per_user_key"
HARD_END = VoiceSession.expiresAt + func.make_interval(
    0, 0, 0, 0, 0, 0, VoiceSession.maxDurationSeconds, type_=Interval()
)
AGENT_OCCUPIED_UNTIL = VoiceSession.startedAt + func.make_interval(
    0, 0, 0, 0, 0, 0, AGENT_OCCUPANCY_SECONDS, type_=Interval()
)


class SqlVoiceStore:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self._sessions = sessions

    async def consented(self, user_id: uuid.UUID, version: str) -> bool:
        async with self._sessions() as session:
            found = await session.scalar(
                select(ConsentRecord.id).where(
                    ConsentRecord.userId == user_id,
                    ConsentRecord.kind == "VOICE_NOTICE",
                    ConsentRecord.noticeVersion == version,
                )
            )
        return found is not None

    async def craft(self, slug: str) -> CraftRef | None:
        async with self._sessions() as session:
            craft = await knowledge_view.resolve_craft(session, slug)
        return None if craft is None else CraftRef.model_validate(knowledge_view.craft_ref(craft))

    async def pack(self, craft: CraftRef, mode: str) -> VoicePack:
        async with self._sessions() as session:
            row = await knowledge_view.resolve_craft(session, craft.slug)
            if row is None:
                return VoicePack(craft=craft, mode=mode, cited=cited_claims([], {}))
            views, sources = await knowledge_view.claims_for(session, row, mode=mode, acls=EVERY_CHUNK_ACLS)
            stages = await session.execute(
                select(ProcessStage.conceptId, ProcessStage.id)
                .join(Process, Process.id == ProcessStage.processId)
                .where(Process.craftId == row.id, ProcessStage.conceptId.is_not(None))
                .order_by(ProcessStage.ordinal)
            )
            stage_of: dict[uuid.UUID, uuid.UUID] = {}
            for concept, stage in stages.tuples().all():
                stage_of.setdefault(concept, stage)
        return VoicePack(craft=craft, mode=mode, cited=cited_claims(views, sources), stage_of=stage_of)

    async def close_lapsed(self, now: datetime) -> int:
        async with self._sessions() as session:
            done = await session.execute(
                update(VoiceSession)
                .where(VoiceSession.endedAt.is_(None), now >= HARD_END)
                .values(**_ending_values(HARD_END))
                .returning(VoiceSession.id)
            )
            closed = len(done.all())
            await session.commit()
        return closed

    async def has_live(self, user_id: uuid.UUID, now: datetime) -> bool:
        async with self._sessions() as session:
            found = await session.scalar(
                select(VoiceSession.id).where(VoiceSession.userId == user_id, _occupying(now)).limit(1)
            )
        return found is not None

    async def live_count(self, now: datetime) -> int:
        async with self._sessions() as session:
            return int(
                await session.scalar(select(func.count()).select_from(VoiceSession).where(_occupying(now)))
                or 0
            )

    async def seconds_used(self, user_id: uuid.UUID, now: datetime) -> int:
        async with self._sessions() as session:
            return await used_today(session, user_id=user_id, resource=VOICE_SECONDS, now=now)

    async def create(self, record: SessionRecord) -> bool:
        async with self._sessions() as session:
            craft_id = await _craft_id(session, record.craft)
            session.add(
                Conversation(
                    id=record.chat_id,
                    userId=record.user_id,
                    craftId=craft_id,
                    mode=record.mode,
                    channel="VOICE",
                    language=record.language,
                )
            )
            session.add(session_row(record, craft_id))
            try:
                await session.commit()
            except IntegrityError as error:
                await session.rollback()
                if LIVE_INDEX not in str(error.orig):
                    raise
                return False
        return True

    async def bind(
        self, session_id: uuid.UUID, *, conversation_id: str, agent_id: str, nonce_hash: str
    ) -> None:
        async with self._sessions() as session:
            await session.execute(
                update(VoiceSession)
                .where(VoiceSession.id == session_id)
                .values(elConversationId=conversation_id, agentId=agent_id, nonceHash=nonce_hash)
            )
            await session.commit()

    async def by_id(self, session_id: uuid.UUID) -> SessionRecord | None:
        return await self._one(VoiceSession.id == session_id)

    async def by_conversation(self, conversation_id: str) -> SessionRecord | None:
        return await self._one(VoiceSession.elConversationId == conversation_id)

    async def begin_turn(self, session_id: uuid.UUID, now: datetime) -> SessionRecord | None:
        async with self._sessions() as session:
            begun = await session.scalar(
                update(VoiceSession)
                .where(VoiceSession.id == session_id, VoiceSession.turnCount < MAX_TURNS, *_live(now))
                .values(turnCount=VoiceSession.turnCount + 1)
                .returning(VoiceSession.id)
            )
            await session.commit()
        return None if begun is None else await self.by_id(session_id)

    async def claim_turn(self, session_id: uuid.UUID, now: datetime, hold: TurnHold) -> TurnClaim:
        async with self._sessions() as session:
            found = (
                await session.execute(
                    select(VoiceSession.userId, User.role)
                    .join(User, User.id == VoiceSession.userId)
                    .where(VoiceSession.id == session_id, VoiceSession.turnCount < MAX_TURNS, *_live(now))
                    .with_for_update(of=VoiceSession)
                )
            ).first()
            if found is None:
                return TurnClaim(None, refusal="ended")
            used = await used_today(session, user_id=found.userId, resource=VOICE_SECONDS, now=now)
            remaining = remaining_today(found.role, VOICE_SECONDS, used)
            if remaining is not None and remaining < hold.least:
                return TurnClaim(None, refusal="quota")
            held = capped_seconds(hold.entry.units, remaining)
            await _add_seconds(session, session_id, replace(hold.entry, units=held))
            await session.execute(
                update(VoiceSession)
                .where(VoiceSession.id == session_id)
                .values(turnCount=VoiceSession.turnCount + 1)
            )
            await session.commit()
        return TurnClaim(await self.by_id(session_id), held=held)

    async def reserve(self, session_id: uuid.UUID, entry: LedgerEntry) -> int:
        async with self._sessions() as session:
            await _add_seconds(session, session_id, entry)
            reserved = await session.scalar(
                select(VoiceSession.reservedSeconds).where(VoiceSession.id == session_id)
            )
            await session.commit()
        return int(reserved or 0)

    async def save_turn(self, session_id: uuid.UUID, save: TurnSave) -> None:
        async with self._sessions() as session:
            row = await session.scalar(
                select(VoiceSession).where(VoiceSession.id == session_id).with_for_update()
            )
            if row is None:
                raise LookupError(f"Voice session {session_id} is gone")
            row.transcriptEnc = save.merge(row.transcriptEnc)
            if save.answer is not None:
                session.add(await answer_row(session, row, save.answer))
            for entry in save.seconds:
                await _add_seconds(session, session_id, entry)
            await session.commit()

    async def end(self, session_id: uuid.UUID, now: datetime) -> SessionRecord | None:
        ended_at = func.least(literal(now, DateTime(timezone=True)), HARD_END, type_=DateTime(timezone=True))
        async with self._sessions() as session:
            await session.execute(
                update(VoiceSession)
                .where(VoiceSession.id == session_id, VoiceSession.endedAt.is_(None))
                .values(**_ending_values(ended_at))
            )
            await session.commit()
        return await self.by_id(session_id)

    async def purge_transcripts(self, now: datetime) -> int:
        async with self._sessions() as session:
            done = await session.execute(
                update(VoiceSession)
                .where(VoiceSession.retentionUntil <= now, VoiceSession.transcriptEnc.is_not(None))
                .values(transcriptEnc=None)
                .returning(VoiceSession.id)
            )
            purged = len(done.all())
            await session.commit()
        return purged

    async def unreconciled(self, limit: int, *, user_id: uuid.UUID | None = None) -> list[SessionRecord]:
        condition = and_(
            VoiceSession.transport == "AGENT",
            VoiceSession.endedAt.is_not(None),
            VoiceSession.billedSeconds.is_(None),
            VoiceSession.elConversationId.is_not(None),
        )
        if user_id is not None:
            condition = and_(condition, VoiceSession.userId == user_id)
        return await self._many(condition, limit)

    async def settle(self, record: SessionRecord, billed: int, entry: LedgerEntry | None) -> None:
        async with self._sessions() as session:
            if entry is not None and await record_units(session, entry):
                await session.execute(
                    update(QuotaLedger)
                    .where(QuotaLedger.idempotencyKey == entry.key)
                    .values(createdAt=record.started_at)
                )
            await session.execute(
                update(VoiceSession).where(VoiceSession.id == record.id).values(billedSeconds=billed)
            )
            await session.commit()

    async def _one(self, condition: Any) -> SessionRecord | None:
        found = await self._many(condition, 1)
        return found[0] if found else None

    async def _many(self, condition: Any, limit: int) -> list[SessionRecord]:
        query = (
            select(VoiceSession, User.role, Craft.slug, Craft.name)
            .join(User, User.id == VoiceSession.userId)
            .outerjoin(Craft, Craft.id == VoiceSession.craftId)
            .where(condition)
            .order_by(VoiceSession.createdAt)
            .limit(limit)
        )
        async with self._sessions() as session:
            rows = (await session.execute(query)).all()
        return [_record(row, role, slug, name) for row, role, slug, name in rows]


def _live(now: datetime) -> tuple[Any, ...]:
    return (VoiceSession.endedAt.is_(None), now < HARD_END)


def _occupying(now: datetime) -> Any:
    unsettled_call = and_(
        VoiceSession.transport == "AGENT",
        VoiceSession.elConversationId.is_not(None),
        VoiceSession.billedSeconds.is_(None),
        now < AGENT_OCCUPIED_UNTIL,
    )
    return or_(and_(*_live(now)), unsettled_call)


def _ending_values(ended_at: Any) -> dict[str, Any]:
    return {
        "endedAt": ended_at,
        "nonceHash": None,
        "retentionUntil": ended_at + func.make_interval(0, 0, 0, TRANSCRIPT_RETENTION_DAYS, type_=Interval()),
        "billedSeconds": case(
            (VoiceSession.transport == "RELAY", VoiceSession.reservedSeconds),
            else_=VoiceSession.billedSeconds,
        ),
    }


async def _add_seconds(session: AsyncSession, session_id: uuid.UUID, entry: LedgerEntry) -> None:
    if await record_units(session, entry):
        await session.execute(
            update(VoiceSession)
            .where(VoiceSession.id == session_id)
            .values(reservedSeconds=VoiceSession.reservedSeconds + entry.units)
        )


async def _craft_id(session: AsyncSession, craft: CraftRef | None) -> uuid.UUID | None:
    if craft is None:
        return None
    row = await knowledge_view.resolve_craft(session, craft.slug)
    return row.id if row else None


async def answer_row(session: AsyncSession, row: VoiceSession, answer: AnswerRecord) -> Answer:
    craft_id = row.craftId
    if answer.craft_slug is not None and craft_id is None:
        resolved = await knowledge_view.resolve_craft(session, answer.craft_slug)
        craft_id = resolved.id if resolved else None
    return Answer(
        id=answer.id,
        conversationId=row.conversationId,
        userId=row.userId,
        question=VOICE_ANSWER_QUESTION,
        language=row.language,
        mode=row.mode,
        craftId=craft_id,
        payload={"channel": "VOICE", "sentences": list(answer.sentences)},
        claimIds=list(answer.claim_ids),
        tiersUsed=VOICE_TIERS,
        latencyMs=answer.latency_ms,
    )


def session_row(record: SessionRecord, craft_id: uuid.UUID | None) -> VoiceSession:
    return VoiceSession(
        id=record.id,
        userId=record.user_id,
        language=record.language,
        craftId=craft_id,
        conversationId=record.chat_id,
        mode=record.mode,
        transport=record.transport,
        startedAt=record.started_at,
        expiresAt=record.expires_at,
        maxDurationSeconds=record.max_duration_seconds,
        retentionUntil=record.hard_end + RETENTION,
        purpose=record.purpose,
    )


def _record(row: VoiceSession, role: str, slug: str | None, name: str | None) -> SessionRecord:
    craft = None if slug is None or name is None else CraftRef(slug=slug, name=name, path=f"/crafts/{slug}")
    return SessionRecord(
        id=row.id,
        user_id=row.userId,
        role=role,
        craft=craft,
        mode=row.mode,
        language=row.language,
        transport=row.transport,
        started_at=row.startedAt or row.createdAt,
        expires_at=row.expiresAt or row.createdAt,
        max_duration_seconds=row.maxDurationSeconds,
        turn_count=row.turnCount,
        reserved_seconds=row.reservedSeconds,
        conversation_id=row.elConversationId,
        agent_id=row.agentId,
        nonce_hash=row.nonceHash,
        chat_id=row.conversationId,
        ended_at=row.endedAt,
        billed_seconds=row.billedSeconds,
        retention_until=row.retentionUntil,
        transcript=row.transcriptEnc,
        purpose=row.purpose,
    )
