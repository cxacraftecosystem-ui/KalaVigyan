from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from app.core.errors import ExternalFailure
from app.providers.elevenlabs import TTS_BITS_PER_SECOND, TimedSpeech
from app.providers.quota import LedgerEntry
from app.research.explainer import Explainer
from app.services.object_store import PresignedGet
from app.voice.listen import ListenAsk, ListenDeps, ListenHold

from ..contracts.golden import golden_json

BUCKET_HOST = "https://kalavigyan-media-example.s3.ap-south-1.amazonaws.com"
VOICE_ID = "voice_1"
LISTENED_AT = datetime(2026, 11, 17, 9, 0, tzinfo=UTC)
LEARNER = uuid.UUID("66ceb1a0-fce2-5527-b3c8-c9c4507c60b9")
SECONDS_PER_CHARACTER = 0.05
BYTES_PER_SECOND = TTS_BITS_PER_SECOND // 8


def golden_explainer(**changes: Any) -> Explainer:
    document = golden_json("explainer.document.golden.json")
    return Explainer.model_validate({**document, **changes})


def uniform_speech(text: str, step: float = SECONDS_PER_CHARACTER) -> TimedSpeech:
    starts = tuple(index * step for index in range(len(text)))
    ends = tuple((index + 1) * step for index in range(len(text)))
    audio = b"\xff" * round(len(text) * step * BYTES_PER_SECOND)
    return TimedSpeech(audio=audio, starts=starts, ends=ends)


@dataclass
class MemoryObjects:
    stored: dict[str, tuple[bytes, str]] = field(default_factory=dict)
    reads: int = 0

    async def get(self, key: str) -> bytes | None:
        self.reads += 1
        found = self.stored.get(key)
        return None if found is None else found[0]

    async def put(self, key: str, body: bytes, *, content_type: str) -> None:
        self.stored[key] = (body, content_type)

    async def put_if_absent(self, key: str, body: bytes, *, content_type: str) -> bool:
        if key in self.stored:
            return False
        self.stored[key] = (body, content_type)
        return True

    async def delete(self, key: str) -> None:
        self.stored.pop(key, None)

    def presigned_get(self, key: str, *, disposition: str, seconds: int, now: datetime) -> PresignedGet:
        assert disposition.startswith("inline; filename=")
        return PresignedGet(
            url=f"{BUCKET_HOST}/{key}?X-Amz-Expires={seconds}", expires_at=now + timedelta(seconds=seconds)
        )


@dataclass
class Narrations:
    calls: list[dict[str, str]] = field(default_factory=list)
    failing: str | None = None
    seconds_per_character: float = SECONDS_PER_CHARACTER

    async def narration(
        self, text: str, *, voice_id: str, language: str, previous_text: str = "", next_text: str = ""
    ) -> TimedSpeech:
        self.calls.append(
            {
                "text": text,
                "voiceId": voice_id,
                "language": language,
                "previous": previous_text,
                "next": next_text,
            }
        )
        if self.failing is not None and self.failing in text:
            raise ExternalFailure("ElevenLabs answered 500", kind="unavailable", service="elevenlabs")
        return uniform_speech(text, self.seconds_per_character)


@dataclass
class MemoryLedger:
    allowance: int | None = 600
    used: int = 0
    rows: list[LedgerEntry] = field(default_factory=list)

    async def hold(self, entry: LedgerEntry, now: datetime) -> ListenHold:
        remaining = None if self.allowance is None else max(0, self.allowance - self.used - self.billed)
        if remaining is not None and remaining < entry.units:
            return ListenHold(held=0, remaining_after=remaining, refused=True)
        self.rows.append(entry)
        return ListenHold(
            held=entry.units, remaining_after=None if remaining is None else remaining - entry.units
        )

    async def record(self, entry: LedgerEntry) -> None:
        self.rows.append(entry)

    @property
    def billed(self) -> int:
        return sum(row.units for row in self.rows)


@dataclass
class Listening:
    objects: MemoryObjects = field(default_factory=MemoryObjects)
    narrator: Narrations = field(default_factory=Narrations)
    ledger: MemoryLedger = field(default_factory=MemoryLedger)

    def deps(self) -> ListenDeps:
        return ListenDeps(
            ledger=self.ledger,
            objects=self.objects,
            narrator=self.narrator,
            voice_id=VOICE_ID,
            clock=lambda: LISTENED_AT,
        )


def ask(explainer: Explainer, section_id: str | None = None, *, request: int = 1) -> ListenAsk:
    return ListenAsk(
        user_id=LEARNER, explainer=explainer, section_id=section_id, request_id=uuid.UUID(int=request)
    )
