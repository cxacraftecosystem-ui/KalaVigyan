import base64
import json
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Any

import httpx

from app.composer.translation import ModelTranslator
from app.providers.quota import LedgerEntry, remaining_today
from app.research.crafts import CraftRef
from app.research.structured import StructuredModel, StructuredReply
from app.services.answer_events import CitedClaims
from app.services.answer_translation import AnswerTranslation
from app.services.knowledge_view import ClaimView
from app.voice.binding import nonce_hash, session_nonce
from app.voice.pack import VoicePack
from app.voice.privacy import TranscriptCipher
from app.voice.records import SessionRecord, TurnClaim, TurnHold, TurnSave
from app.voice.seconds import AGENT_OCCUPANCY_SECONDS, VOICE_SECONDS, capped_seconds
from app.voice.turns import TurnTools

from ..contracts.golden import golden_json

TRANSCRIPT = golden_json("voice.transcript.golden.json")
GOLDEN_TURN = TRANSCRIPT["turns"][0]
SOURCE: dict[str, Any] = TRANSCRIPT["sources"][0]
CITATION: dict[str, Any] = GOLDEN_TURN["sentences"][0]["citations"][0]
SESSION_ID = uuid.UUID(TRANSCRIPT["voiceSessionId"])
TURN_ID = uuid.UUID(GOLDEN_TURN["turnId"])
ANSWER_ID = uuid.UUID(GOLDEN_TURN["answerId"])
CLAIM_ID = uuid.UUID(CITATION["claimId"])
CRAFT = CraftRef.model_validate(TRANSCRIPT["craft"])
ALUM = "Alum is used as a mordant to fasten the colours."
QUESTION = GOLDEN_TURN["heard"]
USER_ID = uuid.UUID("5d0c1f2e-3a4b-4c5d-8e6f-7a8b9c0d1e2f")
STAGE_CONCEPT_ID = uuid.UUID("9a1b2c3d-4e5f-4a6b-8c7d-8e9fa0b1c2d3")
STAGE_ID = uuid.UUID("7b8c9d0e-1f2a-4b3c-9d4e-5f6a7b8c9d0e")
START = datetime(2026, 11, 16, 10, 30, tzinfo=UTC)
TRANSCRIPT_KEY = base64.urlsafe_b64encode(b"voice-test-transcript-key-32byte").decode("ascii")
HMAC_KEY = b"test-only-voice-binding-key-not-a-secret-0123"
BEARER = "test-only-voice-llm-bearer-not-a-secret-0123456789"
CONVERSATION_ID = "conv_0123456789abcdef"


def cipher() -> TranscriptCipher:
    return TranscriptCipher(TRANSCRIPT_KEY)


def alum_view(*, concept_type: str = "MATERIAL", concept_id: uuid.UUID | None = None) -> ClaimView:
    return ClaimView(
        id=CLAIM_ID,
        text=ALUM,
        level="PROVISIONAL",
        concept_type=concept_type,
        concept_id=concept_id,
        citations=[dict(CITATION)],
    )


def alum_pack(
    *views: ClaimView, mode: str = "HYBRID", stage_of: dict[uuid.UUID, uuid.UUID] | None = None
) -> VoicePack:
    chosen = views or (alum_view(),)
    cited = CitedClaims(views={view.id: view for view in chosen}, sources={SOURCE["id"]: dict(SOURCE)})
    return VoicePack(craft=CRAFT, mode=mode, cited=cited, stage_of=stage_of or {})


def session(**changes: Any) -> SessionRecord:
    record = SessionRecord(
        id=SESSION_ID,
        user_id=USER_ID,
        role="STUDENT",
        craft=CRAFT,
        mode="HYBRID",
        language="en",
        transport="RELAY",
        started_at=START,
        expires_at=START + timedelta(seconds=120),
        max_duration_seconds=540,
        chat_id=uuid.UUID("3e4f5a6b-7c8d-4e9f-8a0b-1c2d3e4f5a6b"),
    )
    return replace(record, **changes)


def agent_session(**changes: Any) -> SessionRecord:
    record = session(transport="AGENT", conversation_id=CONVERSATION_ID, agent_id="agent_test", **changes)
    hashed = nonce_hash(session_nonce(HMAC_KEY, record, CONVERSATION_ID))
    return replace(record, nonce_hash=changes.get("nonce_hash", hashed))


def compose_reply(text: str, quote: str, *, ref: uuid.UUID = CLAIM_ID) -> str:
    sentence = {"text": text, "quotes": [{"source": str(ref), "quote": quote}]}
    return json.dumps({"sections": [{"heading": "Answer", "sentences": [sentence]}], "followUps": []})


@dataclass
class FakeModel:
    replies: list[str]
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def __call__(self, *, system: str, user: str, schema: Any) -> StructuredReply:
        self.calls.append({"system": system, "user": user, "schema": schema})
        return StructuredReply(text=self.replies[len(self.calls) - 1], degraded=False)


def translation_reply(**texts: str) -> str:
    return json.dumps(
        {"items": [{"key": key, "text": text} for key, text in texts.items()]}, ensure_ascii=False
    )


@dataclass
class MemoryTranslationCache:
    rows: dict[tuple[uuid.UUID, str], tuple[str, str]] = field(default_factory=dict)

    async def known(self, language: str, texts: dict[uuid.UUID, str]) -> dict[uuid.UUID, str]:
        found = {claim: self.rows.get((claim, language)) for claim in texts}
        return {claim: row[1] for claim, row in found.items() if row is not None and row[0] == texts[claim]}

    async def remember(self, language: str, entries: dict[uuid.UUID, tuple[str, str]]) -> None:
        self.rows.update({(claim, language): entry for claim, entry in entries.items()})


def translation(
    model: StructuredModel | None = None, cache: MemoryTranslationCache | None = None
) -> AnswerTranslation:
    return AnswerTranslation(
        translator=ModelTranslator(model=model or FakeModel([])), cache=cache or MemoryTranslationCache()
    )


def tools(
    pack: VoicePack | None = None,
    *,
    model: FakeModel | None = None,
    resolved: CraftRef | None = None,
    translated: AnswerTranslation | None = None,
) -> TurnTools:
    chosen = pack or alum_pack()

    async def load(craft: CraftRef, mode: str) -> VoicePack:
        return replace(chosen, mode=mode)

    async def resolve(question: str, language: str) -> CraftRef | None:
        return resolved

    return TurnTools(
        pack=load,
        resolve=resolve,
        compose=model or FakeModel([compose_reply(ALUM, ALUM)]),
        translation=translated or translation(),
    )


def ids(*values: uuid.UUID) -> Callable[[], uuid.UUID]:
    queue: Iterator[uuid.UUID] = iter(values)
    return lambda: next(queue)


@dataclass
class MemoryStore:
    sessions: dict[uuid.UUID, SessionRecord] = field(default_factory=dict)
    ledger: dict[str, LedgerEntry] = field(default_factory=dict)
    answers: list[Any] = field(default_factory=list)
    consents: set[tuple[uuid.UUID, str]] = field(default_factory=set)
    crafts: dict[str, CraftRef] = field(default_factory=lambda: {CRAFT.slug: CRAFT})
    packs: dict[str, VoicePack] = field(default_factory=lambda: {CRAFT.slug: alum_pack()})
    pack_acls: list[tuple[str, ...]] = field(default_factory=list)
    used_before: int = 0

    async def consented(self, user_id: uuid.UUID, version: str) -> bool:
        return (user_id, version) in self.consents

    async def craft(self, slug: str) -> CraftRef | None:
        return self.crafts.get(slug)

    async def pack(self, craft: CraftRef, mode: str, acls: tuple[str, ...]) -> VoicePack:
        self.pack_acls.append(acls)
        return replace(self.packs[craft.slug], mode=mode)

    async def close_lapsed(self, now: datetime) -> int:
        lapsed = [r for r in self.sessions.values() if r.ended_at is None and r.hard_end <= now]
        for record in lapsed:
            self.sessions[record.id] = replace(record, ended_at=record.hard_end, nonce_hash=None)
        return len(lapsed)

    async def has_live(self, user_id: uuid.UUID, now: datetime) -> bool:
        return any(r.user_id == user_id and occupying(r, now) for r in self.sessions.values())

    async def live_count(self, now: datetime) -> int:
        return sum(1 for r in self.sessions.values() if occupying(r, now))

    async def seconds_used(self, user_id: uuid.UUID, now: datetime) -> int:
        return self.used_before + sum(e.units for e in self.ledger.values() if e.user_id == user_id)

    async def create(self, record: SessionRecord) -> bool:
        if any(r.user_id == record.user_id and r.ended_at is None for r in self.sessions.values()):
            return False
        self.sessions[record.id] = record
        return True

    async def bind(
        self, session_id: uuid.UUID, *, conversation_id: str, agent_id: str, nonce_hash: str
    ) -> None:
        self.sessions[session_id] = replace(
            self.sessions[session_id],
            conversation_id=conversation_id,
            agent_id=agent_id,
            nonce_hash=nonce_hash,
        )

    async def by_id(self, session_id: uuid.UUID) -> SessionRecord | None:
        return self.sessions.get(session_id)

    async def by_conversation(self, conversation_id: str) -> SessionRecord | None:
        return next((r for r in self.sessions.values() if r.conversation_id == conversation_id), None)

    async def begin_turn(self, session_id: uuid.UUID, now: datetime) -> SessionRecord | None:
        record = self.sessions[session_id]
        if not record.live_at(now) or record.turn_count >= 40:
            return None
        self.sessions[session_id] = replace(record, turn_count=record.turn_count + 1)
        return self.sessions[session_id]

    async def claim_turn(self, session_id: uuid.UUID, now: datetime, hold: TurnHold) -> TurnClaim:
        record = self.sessions[session_id]
        if not record.live_at(now) or record.turn_count >= 40:
            return TurnClaim(None, refusal="ended")
        remaining = remaining_today(record.role, VOICE_SECONDS, await self.seconds_used(record.user_id, now))
        if remaining is not None and remaining < hold.least:
            return TurnClaim(None, refusal="quota")
        held = capped_seconds(hold.entry.units, remaining)
        self._add(session_id, replace(hold.entry, units=held))
        self.sessions[session_id] = replace(self.sessions[session_id], turn_count=record.turn_count + 1)
        return TurnClaim(self.sessions[session_id], held=held)

    async def reserve(self, session_id: uuid.UUID, entry: LedgerEntry) -> int:
        self._add(session_id, entry)
        return self.sessions[session_id].reserved_seconds

    async def save_turn(self, session_id: uuid.UUID, save: TurnSave) -> None:
        record = self.sessions[session_id]
        self.sessions[session_id] = replace(record, transcript=save.merge(record.transcript))
        if save.answer is not None:
            self.answers.append(save.answer)
        for entry in save.seconds:
            self._add(session_id, entry)

    async def end(self, session_id: uuid.UUID, now: datetime) -> SessionRecord | None:
        record = self.sessions[session_id]
        if record.ended_at is None:
            ended = min(now, record.hard_end)
            billed = record.reserved_seconds if record.transport == "RELAY" else record.billed_seconds
            self.sessions[session_id] = replace(
                record,
                ended_at=ended,
                nonce_hash=None,
                billed_seconds=billed,
                retention_until=ended + timedelta(days=30),
            )
        return self.sessions[session_id]

    async def purge_transcripts(self, now: datetime) -> int:
        purged = [
            r
            for r in self.sessions.values()
            if r.transcript and r.retention_until and r.retention_until <= now
        ]
        for record in purged:
            self.sessions[record.id] = replace(record, transcript=None)
        return len(purged)

    async def unreconciled(self, limit: int, *, user_id: uuid.UUID | None = None) -> list[SessionRecord]:
        return [
            r
            for r in self.sessions.values()
            if r.transport == "AGENT"
            and r.ended_at
            and r.billed_seconds is None
            and r.conversation_id
            and user_id in (None, r.user_id)
        ][:limit]

    async def settle(self, record: SessionRecord, billed: int, entry: LedgerEntry | None) -> None:
        if entry is not None:
            self.ledger.setdefault(entry.key, entry)
        self.sessions[record.id] = replace(self.sessions[record.id], billed_seconds=billed)

    def _add(self, session_id: uuid.UUID, entry: LedgerEntry) -> None:
        if entry.key in self.ledger:
            return
        self.ledger[entry.key] = entry
        record = self.sessions[session_id]
        self.sessions[session_id] = replace(record, reserved_seconds=record.reserved_seconds + entry.units)


def occupying(record: SessionRecord, now: datetime) -> bool:
    if record.live_at(now):
        return True
    unsettled = record.transport == "AGENT" and record.conversation_id and record.billed_seconds is None
    return bool(unsettled) and now < record.started_at + timedelta(seconds=AGENT_OCCUPANCY_SECONDS)


def recorded_transport(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))
