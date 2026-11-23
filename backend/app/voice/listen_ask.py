from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol

from app.core.errors import Refused
from app.core.shielded import ShieldedWork
from app.providers.quota import LedgerEntry
from app.research.explainer import Explainer
from app.schemas.listen import ListenVoiceName

from .listen_voices import ListenVoice
from .object_lease import LeasedObjects
from .seconds import VOICE_SECONDS

__all__ = [
    "LISTEN_LEDGER_REF",
    "Admission",
    "ListenAsk",
    "ListenDeps",
    "ListenHold",
    "ListenLedger",
    "ListenRefused",
    "admitted",
]

LISTEN_LEDGER_REF = "Answer"

Admission = Callable[[], Awaitable[None]]


class ListenRefused(Refused):
    def __init__(self, reason: str, message: str, *, retry_after: int | None = None) -> None:
        super().__init__(reason, message)
        self.retry_after = retry_after


@dataclass(frozen=True)
class ListenHold:
    held: int
    remaining_after: int | None
    refused: bool = False


class ListenLedger(Protocol):
    async def hold(self, entry: LedgerEntry, now: datetime) -> ListenHold: ...

    async def record(self, entry: LedgerEntry) -> None: ...


async def admitted() -> None:
    return None


@dataclass(frozen=True)
class ListenDeps:
    ledger: ListenLedger
    objects: LeasedObjects
    voices: tuple[ListenVoice, ...]
    clock: Callable[[], datetime]
    shield: ShieldedWork
    admit: Admission = admitted
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep


@dataclass(frozen=True)
class ListenAsk:
    user_id: uuid.UUID
    explainer: Explainer
    section_id: str | None
    voice: ListenVoiceName | None = None
    request_id: uuid.UUID = field(default_factory=uuid.uuid4)

    @property
    def language(self) -> str:
        return self.explainer.understood.language

    def entry(self, units: int, key: str) -> LedgerEntry:
        return LedgerEntry(
            user_id=self.user_id,
            resource=VOICE_SECONDS,
            units=units,
            key=key,
            ref_type=LISTEN_LEDGER_REF,
            ref_id=str(self.explainer.answer_id),
        )
