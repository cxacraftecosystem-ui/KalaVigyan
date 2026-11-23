from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any, Protocol

from pydantic import TypeAdapter

from app.core.errors import AppError, Refused
from app.core.roles import Capability, can
from app.providers.quota import remaining_today, seconds_until_next_day
from app.research.crafts import CraftRef
from app.research.retrieval import chunk_acls_for
from app.schemas.voice import (
    MAX_SESSION_SECONDS,
    MAX_TURNS,
    MIN_START_SECONDS,
    RELAY_AUDIO_BITS_PER_SECOND,
    RELAY_AUDIO_TYPES,
    RELAY_MAX_AUDIO_BYTES,
    RELAY_MAX_TURN_SECONDS,
    VoiceSessionEnded,
    VoiceSessionStarted,
)

from .binding import nonce_hash, session_nonce
from .languages import VOICE_LANGUAGES
from .notice import VOICE_NOTICE_VERSION
from .records import SessionRecord, VoiceStore
from .runtime import VoiceRuntime, VoiceSettings
from .seconds import START_WINDOW_SECONDS, VOICE_SECONDS, agent_hold_key, ledger_entry
from .upkeep import settle_own_calls

__all__ = [
    "BUSY_RETRY_SECONDS",
    "MESSAGES",
    "VOICE_CONSENT_HEADER",
    "StartAsk",
    "VoiceRefused",
    "VoiceUser",
    "end_session",
    "may_use_voice",
    "owned_session",
    "start_session",
]

VOICE_CONSENT_HEADER = "X-Voice-Consent-Required"
BUSY_RETRY_SECONDS = 30
STARTED = TypeAdapter(VoiceSessionStarted)
ENDED = TypeAdapter(VoiceSessionEnded)

MESSAGES = {
    "unverified_email": "Verify your email address to use voice.",
    "consent": "Accept the voice notice to start a call.",
    "language": "Voice does not speak that language.",
    "craft": "No craft has that address.",
    "not_configured": "Voice is not available right now.",
    "live_session": "Your last voice call is still open. End it, or try again in a minute.",
    "quota": "You have used today's voice time. It renews at midnight India time.",
    "busy": "Voice is busy right now. Try again in a minute.",
    "not_found": "No voice call has that address.",
    "speech_gone": "That reply can no longer be played.",
}


class VoiceRefused(Refused):
    def __init__(self, reason: str, *, retry_after: int | None = None, message: str | None = None) -> None:
        super().__init__(reason, message or MESSAGES[reason])
        self.retry_after = retry_after


class VoiceUser(Protocol):
    id: uuid.UUID
    role: str
    emailVerifiedAt: datetime | None


@dataclass(frozen=True)
class StartAsk:
    user: VoiceUser
    craft_slug: str | None
    mode: str
    language: str


def may_use_voice(user: VoiceUser) -> bool:
    return can(user, Capability.VOICE) and user.emailVerifiedAt is not None


async def start_session(
    ask: StartAsk, *, store: VoiceStore, runtime: VoiceRuntime, voice: VoiceSettings, now: datetime
) -> dict[str, Any]:
    craft = await _checked_caller(ask, store)
    if voice.missing() or not await runtime.reachable(voice):
        raise VoiceRefused("not_configured")
    await settle_own_calls(ask.user.id, store, runtime.elevenlabs(voice))
    remaining = await _checked_room(ask.user, store, voice, now)
    if craft is not None:
        await runtime.packs.get(craft, ask.mode, chunk_acls_for(ask.user.role), store.pack)
    record = await _created(
        ask, store, craft=craft, remaining=remaining, transport=voice.transport or "", now=now
    )
    payload = _started_payload(record, remaining)
    if voice.transport == "AGENT":
        payload |= {
            "transport": "AGENT",
            "conversationToken": await _bound(record, store, runtime, voice, now),
        }
    else:
        payload |= {
            "transport": "RELAY",
            "maxTurnSeconds": RELAY_MAX_TURN_SECONDS,
            "maxAudioBytes": RELAY_MAX_AUDIO_BYTES,
            "audioBitsPerSecond": RELAY_AUDIO_BITS_PER_SECOND,
            "audioTypes": list(RELAY_AUDIO_TYPES),
        }
    return STARTED.dump_python(STARTED.validate_python(payload), mode="json", by_alias=True)


async def owned_session(store: VoiceStore, user: VoiceUser, session_id: uuid.UUID) -> SessionRecord:
    record = await store.by_id(session_id)
    if record is None or record.user_id != user.id:
        raise VoiceRefused("not_found")
    return record


async def end_session(
    store: VoiceStore, user: VoiceUser, session_id: uuid.UUID, *, now: datetime
) -> dict[str, Any]:
    record = await owned_session(store, user, session_id)
    if record.ended_at is None:
        record = await store.end(session_id, now) or record
    payload = {
        "voiceSessionId": str(record.id),
        "endedAt": (record.ended_at or now).isoformat(),
        "turnCount": record.turn_count,
        "reservedSeconds": record.reserved_seconds,
        "billedSeconds": record.billed_seconds,
    }
    return ENDED.dump_python(ENDED.validate_python(payload), mode="json", by_alias=True)


async def _checked_caller(ask: StartAsk, store: VoiceStore) -> CraftRef | None:
    if not can(ask.user, Capability.VOICE):
        raise VoiceRefused("capability", message="Your role does not include voice.")
    if ask.user.emailVerifiedAt is None:
        raise VoiceRefused("unverified_email")
    if not await store.consented(ask.user.id, VOICE_NOTICE_VERSION):
        raise VoiceRefused("consent")
    if ask.language not in VOICE_LANGUAGES:
        raise VoiceRefused("language")
    if ask.craft_slug is None:
        return None
    craft = await store.craft(ask.craft_slug)
    if craft is None:
        raise VoiceRefused("craft")
    return craft


async def _checked_room(
    user: VoiceUser, store: VoiceStore, voice: VoiceSettings, now: datetime
) -> int | None:
    await store.close_lapsed(now)
    if await store.has_live(user.id, now):
        raise VoiceRefused("live_session")
    remaining = remaining_today(user, VOICE_SECONDS, await store.seconds_used(user.id, now))
    if remaining is not None and remaining < MIN_START_SECONDS:
        raise VoiceRefused("quota", retry_after=seconds_until_next_day(now))
    if await store.live_count(now) >= voice.max_live_sessions:
        raise VoiceRefused("busy", retry_after=BUSY_RETRY_SECONDS)
    return remaining


async def _created(
    ask: StartAsk,
    store: VoiceStore,
    *,
    craft: CraftRef | None,
    remaining: int | None,
    transport: str,
    now: datetime,
) -> SessionRecord:
    record = SessionRecord(
        id=uuid.uuid4(),
        user_id=ask.user.id,
        role=ask.user.role,
        craft=craft,
        mode=ask.mode,
        language=ask.language,
        transport=transport,
        started_at=now,
        expires_at=now + timedelta(seconds=START_WINDOW_SECONDS),
        max_duration_seconds=MAX_SESSION_SECONDS
        if remaining is None
        else min(MAX_SESSION_SECONDS, remaining),
        chat_id=uuid.uuid4(),
    )
    if not await store.create(record):
        raise VoiceRefused("live_session")
    return record


async def _bound(
    record: SessionRecord, store: VoiceStore, runtime: VoiceRuntime, voice: VoiceSettings, now: datetime
) -> str:
    try:
        token = await runtime.elevenlabs(voice).conversation_token(voice.agent_id or "")
    except AppError:
        await store.end(record.id, now)
        raise
    bound = replace(record, conversation_id=token.conversation_id)
    hashed = nonce_hash(session_nonce(voice.hmac_key or b"", bound, token.conversation_id))
    await store.bind(
        record.id, conversation_id=token.conversation_id, agent_id=voice.agent_id or "", nonce_hash=hashed
    )
    hold = ledger_entry(record, units=record.max_duration_seconds, key=agent_hold_key(record.id))
    await store.reserve(record.id, hold)
    return token.token


def _started_payload(record: SessionRecord, remaining: int | None) -> dict[str, Any]:
    return {
        "voiceSessionId": str(record.id),
        "mode": record.mode,
        "language": record.language,
        "craft": record.craft.model_dump(mode="json", by_alias=True) if record.craft else None,
        "maxDurationSeconds": record.max_duration_seconds,
        "remainingSeconds": remaining,
        "maxTurns": MAX_TURNS,
        "expiresAt": record.expires_at.isoformat(),
    }
