from __future__ import annotations

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from typing import Any

from pydantic import TypeAdapter

from app.core.errors import AppError, Refused
from app.core.roles import Capability, can
from app.providers.elevenlabs import speech_seconds
from app.providers.quota import remaining_today
from app.research.crafts import CraftRef
from app.research.testimony import RECORDING_NOTICE_VERSION
from app.schemas.artisan import ConversationEnded, ConversationStarted, TranscriptTurn, artisan_speech_path
from app.schemas.voice import (
    MAX_SESSION_SECONDS,
    MAX_TURNS,
    RELAY_AUDIO_BITS_PER_SECOND,
    RELAY_AUDIO_TYPES,
    RELAY_MAX_AUDIO_BYTES,
    RELAY_MAX_TURN_SECONDS,
)

from .artisan_guide import agent_opening, guide_question, next_topic, opening
from .artisan_records import ARTISAN_PURPOSE, ArtisanFacts, ArtisanStore, ConversationRecord, NewConversation
from .artisan_transcript import artisan_turns, open_transcript
from .binding import ARTISAN_NONCE_CONTEXT, nonce_hash, session_nonce
from .languages import VOICE_LANGUAGES
from .privacy import TranscriptCipher
from .records import SessionRecord, VoiceStore
from .reply_audio import ReplyAudio
from .runtime import VoiceRuntime, VoiceSettings
from .seconds import (
    START_WINDOW_SECONDS,
    VOICE_SECONDS,
    agent_hold_key,
    capped_seconds,
    ledger_entry,
    relay_speech_key,
)
from .sessions import BUSY_RETRY_SECONDS, VoiceUser

__all__ = [
    "ARTISAN_MESSAGES",
    "RECORDING_CONSENT_HEADER",
    "ArtisanRefused",
    "ConversationDeps",
    "StartConversation",
    "artisan_voice",
    "end_conversation",
    "start_conversation",
]

RECORDING_CONSENT_HEADER = "X-Recording-Consent-Required"
VERIFIED = "VERIFIED"
STARTED = TypeAdapter(ConversationStarted)
ENDED = TypeAdapter(ConversationEnded)

ARTISAN_MESSAGES = {
    "capability": "Conversations about a craft are for artisans.",
    "unverified_email": "Verify your email address to talk with KalaVigyan.",
    "consent": "Agree to the recording notice before you start.",
    "language": "KalaVigyan does not speak that language yet.",
    "craft": "Choose one of your crafts.",
    "not_configured": "Conversations are not available right now.",
    "live_session": "Your last conversation is still open. End it, or try again in a minute.",
    "quota": "You have used today's voice time. It renews at midnight India time.",
    "busy": "KalaVigyan is busy right now. Try again in a minute.",
    "not_found": "No conversation has that address.",
    "speech_gone": "That reply can no longer be played.",
}


class ArtisanRefused(Refused):
    def __init__(self, reason: str, *, retry_after: int | None = None) -> None:
        super().__init__(reason, ARTISAN_MESSAGES[reason])
        self.retry_after = retry_after


@dataclass(frozen=True)
class StartConversation:
    user: VoiceUser
    craft_slug: str
    language: str
    notice_version: str


@dataclass(frozen=True)
class ConversationDeps:
    store: VoiceStore
    artisans: ArtisanStore
    runtime: VoiceRuntime
    voice: VoiceSettings
    cipher: TranscriptCipher
    speech: ReplyAudio
    clock: Callable[[], datetime]
    ids: Callable[[], uuid.UUID] = field(default=uuid.uuid4)


def artisan_voice(voice: VoiceSettings, artisan_agent_id: str | None) -> VoiceSettings:
    agent = (artisan_agent_id or "").strip() or None
    if voice.transport == "AGENT" and agent is None:
        return replace(voice, transport="RELAY", agent_id=None)
    return replace(voice, agent_id=agent)


async def start_conversation(ask: StartConversation, deps: ConversationDeps) -> dict[str, Any]:
    facts, consent_id = await _checked_artisan(ask, deps.artisans)
    craft_id, craft = await _checked_craft(ask, facts, deps.artisans)
    voice = deps.voice
    if voice.missing() or not await deps.runtime.reachable(voice):
        raise ArtisanRefused("not_configured")
    now = deps.clock()
    remaining = await _checked_room(ask.user, deps.store, voice, now)
    record = _session(ask, craft, transport=voice.transport or "", now=now, ids=deps.ids)
    earlier = await deps.artisans.topics_asked_before(ask.user.id, craft_id)
    turn, topics = _opening_turn(record, craft, earlier, deps.ids())
    created = await deps.artisans.start(
        NewConversation(
            session=record,
            conversation_id=deps.ids(),
            craft_id=craft_id,
            consent_record_id=consent_id,
            consent_version=RECORDING_NOTICE_VERSION,
            transcript=deps.cipher.seal(_sealed_turns(turn)),
            topics_asked=topics,
        )
    )
    if not created:
        raise ArtisanRefused("live_session")
    conversation = await deps.artisans.by_voice_session(record.id)
    if conversation is None:
        raise ArtisanRefused("not_found")
    await deps.runtime.packs.get(craft, VERIFIED, deps.store.pack)
    payload = _started_payload(conversation, record, remaining)
    if voice.transport == "AGENT":
        payload |= {"transport": "AGENT", "conversationToken": await _bound(record, deps, now)}
    else:
        await _spoken_opening(record, turn, deps)
        payload |= _relay_payload(conversation, turn)
    return STARTED.dump_python(STARTED.validate_python(payload), mode="json", by_alias=True)


async def end_conversation(
    conversation: ConversationRecord, deps: ConversationDeps, *, now: datetime
) -> tuple[dict[str, Any], ConversationRecord]:
    session = await deps.store.by_id(conversation.voice_session_id) if conversation.voice_session_id else None
    if session is not None and session.ended_at is None:
        session = await deps.store.end(session.id, now) or session
    spoke = bool(artisan_turns(open_transcript(deps.cipher, conversation.transcript)))
    finished = await deps.artisans.finish(conversation.id, now, spoke=spoke) or conversation
    payload = {
        "conversationId": str(finished.id),
        "endedAt": (finished.ended_at or now).isoformat(),
        "turnCount": session.turn_count if session else 0,
        "billedSeconds": session.billed_seconds if session else None,
        "extraction": "NONE" if finished.extraction == "NONE" else "PENDING",
    }
    return ENDED.dump_python(ENDED.validate_python(payload), mode="json", by_alias=True), finished


async def _checked_artisan(ask: StartConversation, artisans: ArtisanStore) -> tuple[ArtisanFacts, uuid.UUID]:
    if not can(ask.user, Capability.CONTRIBUTE_TESTIMONY) or ask.user.emailVerifiedAt is None:
        raise ArtisanRefused("capability" if ask.user.emailVerifiedAt is not None else "unverified_email")
    facts = await artisans.facts(ask.user.id)
    if facts.consent is None or facts.consent[1] != RECORDING_NOTICE_VERSION:
        raise ArtisanRefused("consent")
    if ask.notice_version != RECORDING_NOTICE_VERSION:
        raise ArtisanRefused("consent")
    if ask.language not in VOICE_LANGUAGES:
        raise ArtisanRefused("language")
    return facts, facts.consent[0]


async def _checked_craft(
    ask: StartConversation, facts: ArtisanFacts, artisans: ArtisanStore
) -> tuple[uuid.UUID, CraftRef]:
    craft_id = await artisans.craft_id(ask.craft_slug)
    craft = facts.craft(craft_id) if craft_id else None
    if craft_id is None or craft is None:
        raise ArtisanRefused("craft")
    return craft_id, craft


async def _checked_room(
    user: VoiceUser, store: VoiceStore, voice: VoiceSettings, now: datetime
) -> int | None:
    await store.close_lapsed(now)
    if await store.has_live(user.id, now):
        raise ArtisanRefused("live_session")
    remaining = remaining_today(user, VOICE_SECONDS, await store.seconds_used(user.id, now))
    if await store.live_count(now) >= voice.max_live_sessions:
        raise ArtisanRefused("busy", retry_after=BUSY_RETRY_SECONDS)
    return remaining


def _session(
    ask: StartConversation,
    craft: CraftRef,
    *,
    transport: str,
    now: datetime,
    ids: Callable[[], uuid.UUID],
) -> SessionRecord:
    return SessionRecord(
        id=ids(),
        user_id=ask.user.id,
        role=ask.user.role,
        craft=craft,
        mode=VERIFIED,
        language=ask.language,
        transport=transport,
        started_at=now,
        expires_at=now + timedelta(seconds=START_WINDOW_SECONDS),
        max_duration_seconds=MAX_SESSION_SECONDS,
        chat_id=ids(),
        purpose=ARTISAN_PURPOSE,
    )


def _opening_turn(
    record: SessionRecord, craft: CraftRef, earlier: tuple[str, ...], turn_id: uuid.UUID
) -> tuple[TranscriptTurn, tuple[str, ...]]:
    language = record.language
    if record.transport == "AGENT":
        topic, text = "PROCESS", agent_opening(language)
    else:
        topic = next_topic(earlier) or "PROCESS"
        text = f"{opening(language, craft.name)} {guide_question(topic, language)}"
    asked = earlier if next_topic(earlier) is not None else ()
    turn = TranscriptTurn(
        id=turn_id,
        ordinal=0,
        speaker="KALAVIGYAN",
        text=text,
        english=guide_question(topic, "en"),
        topic=topic,
        start_ms=0,
        end_ms=0,
    )
    return turn, tuple(dict.fromkeys([*asked, topic]))


def _sealed_turns(turn: TranscriptTurn) -> dict[str, Any]:
    return {"version": 1, "turns": [turn.model_dump(mode="json", by_alias=True)]}


async def _spoken_opening(record: SessionRecord, turn: TranscriptTurn, deps: ConversationDeps) -> None:
    try:
        audio = await deps.runtime.elevenlabs(deps.voice).speech(
            turn.text, voice_id=deps.voice.voice_id, language=record.language
        )
    except AppError:
        return
    remaining = remaining_today(
        record.role, VOICE_SECONDS, await deps.store.seconds_used(record.user_id, deps.clock())
    )
    units = capped_seconds(speech_seconds(len(audio)), remaining)
    await deps.store.reserve(
        record.id, ledger_entry(record, units=units, key=relay_speech_key(record.id, turn.id))
    )
    await deps.speech.put(record.id, turn.id, audio)


async def _bound(record: SessionRecord, deps: ConversationDeps, now: datetime) -> str:
    voice = deps.voice
    try:
        token = await deps.runtime.elevenlabs(voice).conversation_token(voice.agent_id or "")
    except AppError:
        await deps.store.end(record.id, now)
        raise
    bound = replace(record, conversation_id=token.conversation_id)
    nonce = session_nonce(voice.hmac_key or b"", bound, token.conversation_id, context=ARTISAN_NONCE_CONTEXT)
    await deps.store.bind(
        record.id,
        conversation_id=token.conversation_id,
        agent_id=voice.agent_id or "",
        nonce_hash=nonce_hash(nonce),
    )
    await deps.store.reserve(
        record.id, ledger_entry(record, units=record.max_duration_seconds, key=agent_hold_key(record.id))
    )
    return token.token


def _started_payload(
    conversation: ConversationRecord, record: SessionRecord, remaining: int | None
) -> dict[str, Any]:
    return {
        "conversationId": str(conversation.id),
        "voiceSessionId": str(record.id),
        "craft": conversation.craft.model_dump(mode="json", by_alias=True),
        "language": record.language,
        "maxDurationSeconds": record.max_duration_seconds,
        "remainingSeconds": remaining,
        "maxTurns": MAX_TURNS,
        "expiresAt": record.expires_at.isoformat(),
    }


def _relay_payload(conversation: ConversationRecord, turn: TranscriptTurn) -> dict[str, Any]:
    return {
        "transport": "RELAY",
        "maxTurnSeconds": RELAY_MAX_TURN_SECONDS,
        "maxAudioBytes": RELAY_MAX_AUDIO_BYTES,
        "audioBitsPerSecond": RELAY_AUDIO_BITS_PER_SECOND,
        "audioTypes": list(RELAY_AUDIO_TYPES),
        "opening": {
            "turnId": str(turn.id),
            "text": turn.text,
            "speechPath": artisan_speech_path(conversation.id, turn.id),
        },
    }
