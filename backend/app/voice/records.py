from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Protocol

from app.providers.quota import LedgerEntry
from app.research.crafts import CraftRef

from .pack import VoicePack

__all__ = ["AnswerRecord", "SessionRecord", "TurnClaim", "TurnHold", "TurnSave", "VoiceStore"]


@dataclass(frozen=True)
class SessionRecord:
    id: uuid.UUID
    user_id: uuid.UUID
    role: str
    craft: CraftRef | None
    mode: str
    language: str
    transport: str
    started_at: datetime
    expires_at: datetime
    max_duration_seconds: int
    turn_count: int = 0
    reserved_seconds: int = 0
    conversation_id: str | None = None
    agent_id: str | None = None
    nonce_hash: str | None = None
    chat_id: uuid.UUID | None = None
    ended_at: datetime | None = None
    billed_seconds: int | None = None
    retention_until: datetime | None = None
    transcript: str | None = None
    purpose: str = "ASK"

    @property
    def hard_end(self) -> datetime:
        return self.expires_at + timedelta(seconds=self.max_duration_seconds)

    @property
    def nonce_exp(self) -> int:
        return int(self.hard_end.timestamp())

    def live_at(self, now: datetime) -> bool:
        return self.ended_at is None and now < self.hard_end


@dataclass(frozen=True)
class AnswerRecord:
    id: uuid.UUID
    craft_slug: str | None
    claim_ids: tuple[uuid.UUID, ...]
    sentences: tuple[dict[str, Any], ...]
    latency_ms: int


@dataclass(frozen=True)
class TurnHold:
    entry: LedgerEntry
    least: int


@dataclass(frozen=True)
class TurnClaim:
    session: SessionRecord | None
    held: int = 0
    refusal: str | None = None


@dataclass(frozen=True)
class TurnSave:
    merge: Callable[[str | None], str]
    answer: AnswerRecord | None = None
    seconds: tuple[LedgerEntry, ...] = field(default_factory=tuple)


class VoiceStore(Protocol):
    async def consented(self, user_id: uuid.UUID, version: str) -> bool: ...

    async def craft(self, slug: str) -> CraftRef | None: ...

    async def pack(self, craft: CraftRef, mode: str, acls: tuple[str, ...]) -> VoicePack: ...

    async def close_lapsed(self, now: datetime) -> int: ...

    async def has_live(self, user_id: uuid.UUID, now: datetime) -> bool: ...

    async def live_count(self, now: datetime) -> int: ...

    async def seconds_used(self, user_id: uuid.UUID, now: datetime) -> int: ...

    async def create(self, record: SessionRecord) -> bool: ...

    async def bind(
        self, session_id: uuid.UUID, *, conversation_id: str, agent_id: str, nonce_hash: str
    ) -> None: ...

    async def by_id(self, session_id: uuid.UUID) -> SessionRecord | None: ...

    async def by_conversation(self, conversation_id: str) -> SessionRecord | None: ...

    async def begin_turn(self, session_id: uuid.UUID, now: datetime) -> SessionRecord | None: ...

    async def claim_turn(self, session_id: uuid.UUID, now: datetime, hold: TurnHold) -> TurnClaim: ...

    async def reserve(self, session_id: uuid.UUID, entry: LedgerEntry) -> int: ...

    async def save_turn(self, session_id: uuid.UUID, save: TurnSave) -> None: ...

    async def end(self, session_id: uuid.UUID, now: datetime) -> SessionRecord | None: ...

    async def unreconciled(self, limit: int, *, user_id: uuid.UUID | None = None) -> list[SessionRecord]: ...

    async def settle(self, record: SessionRecord, billed: int, entry: LedgerEntry | None) -> None: ...
