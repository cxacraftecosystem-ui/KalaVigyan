from __future__ import annotations

import asyncio
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime

from app.schemas.voice import MAX_SESSION_SECONDS, MAX_TURNS
from app.schemas.voice_llm import LlmChatRequest

from .binding import bearer_matches, session_is_bound
from .llm import AgentReply, EndCall
from .phrases import END_CALL_REPLIES, phrase
from .privacy import TranscriptCipher, heard_text
from .records import SessionRecord, TurnSave, VoiceStore
from .runtime import VoiceSettings
from .sessions import VoiceRefused
from .transcript import turn_merge
from .turns import TurnAsk, TurnTools, spoken_turn

__all__ = [
    "CONVERSATION_ID_MAX_CHARS",
    "REFUSAL_CHECKS",
    "AgentCall",
    "agent_reply",
    "authorised_session",
    "last_question",
]

CONVERSATION_ID_MAX_CHARS = 120
ASK_PURPOSE = "ASK"
AGENT_TRANSPORT = "AGENT"
REFUSAL_CHECKS = ("bearer", "conversation header", "session record", "binding")
ELEVENLABS_CONVERSATION_PREFIX = "conv_"
BIND_READ_SECONDS = 0.5
BIND_REREADS = 4
Clock = Callable[[], datetime]
Sleep = Callable[[float], Awaitable[None]]
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentCall:
    authorization: str | None
    conversation_id: str | None


async def authorised_session(
    store: VoiceStore, voice: VoiceSettings, call: AgentCall, *, now: datetime, sleep: Sleep = asyncio.sleep
) -> SessionRecord:
    conversation_id = (call.conversation_id or "").strip()
    if not bearer_matches(call.authorization, voice.llm_bearer) or voice.hmac_key is None:
        raise _refused("bearer", _bearer_detail(call.authorization, voice))
    if not conversation_id or len(conversation_id) > CONVERSATION_ID_MAX_CHARS:
        raise _refused("conversation header", f"{len(conversation_id)} characters")
    record = await _held_record(store, conversation_id, sleep)
    if record is None:
        raise _refused("session record", _unheld_detail(conversation_id))
    unfit = _unfit(record, now)
    if unfit:
        raise _refused("session record", unfit)
    if not session_is_bound(voice.hmac_key, record, conversation_id):
        raise _refused("binding", "the stored nonce or conversation does not match")
    return record


async def _held_record(store: VoiceStore, conversation_id: str, sleep: Sleep) -> SessionRecord | None:
    record = await store.by_conversation(conversation_id)
    if not _names_a_conversation(conversation_id):
        return record
    for _ in range(BIND_REREADS):
        if record is not None:
            return record
        await sleep(BIND_READ_SECONDS)
        record = await store.by_conversation(conversation_id)
    return record


def _names_a_conversation(conversation_id: str) -> bool:
    return conversation_id.startswith(ELEVENLABS_CONVERSATION_PREFIX)


def _unheld_detail(conversation_id: str) -> str:
    size = f"{len(conversation_id)} characters"
    prefix = ELEVENLABS_CONVERSATION_PREFIX
    if not _names_a_conversation(conversation_id):
        return f"no session holds this conversation ({size}, does not start with {prefix})"
    waited = BIND_READ_SECONDS * BIND_REREADS
    return f"no session held this conversation within {waited:g} s ({size}, starts with {prefix})"


def _refused(check: str, detail: str) -> VoiceRefused:
    logger.warning("a voice agent turn was refused at the %s check: %s", check, detail)
    return VoiceRefused("unauthorized", message="unauthorized")


def _bearer_detail(authorization: str | None, voice: VoiceSettings) -> str:
    if voice.hmac_key is None:
        return "no session key is configured"
    if not (voice.llm_bearer or "").strip():
        return "no agent bearer is configured"
    if not authorization:
        return "the request carried no authorization header"
    if not authorization.startswith("Bearer "):
        return "the authorization header is not a bearer"
    return "the bearer differs from the configured one"


def _unfit(record: SessionRecord, now: datetime) -> str:
    if record.purpose != ASK_PURPOSE:
        return f"its purpose is {record.purpose}"
    if record.transport != AGENT_TRANSPORT:
        return f"its transport is {record.transport}"
    if not record.live_at(now):
        return "it has ended" if record.ended_at is not None else "it is past its hard end"
    if record.turn_count > MAX_TURNS:
        return f"it has had {record.turn_count} turns"
    return ""


def last_question(request: LlmChatRequest) -> str:
    asked = next(m for m in reversed(request.messages) if m.role == "user")
    return heard_text(asked.content or "")


async def agent_reply(
    record: SessionRecord,
    question: str,
    *,
    store: VoiceStore,
    tools: TurnTools,
    cipher: TranscriptCipher,
    clock: Clock,
    ids: Callable[[], uuid.UUID] = uuid.uuid4,
) -> AgentReply:
    if not question:
        return AgentReply()
    now = clock()
    ending = _ending(record, now)
    if ending is not None:
        await store.end(record.id, now)
        return AgentReply(end_call=ending)
    begun = await store.begin_turn(record.id, now)
    if begun is None:
        return AgentReply(end_call=_end_call("turns", record.language))
    started = time.perf_counter()
    turn = await spoken_turn(TurnAsk.begun(begun, question, turn_id=ids(), answer_id=ids(), now=now), tools)
    merge, _ = turn_merge(cipher, turn)
    latency = round((time.perf_counter() - started) * 1000)
    await store.save_turn(record.id, TurnSave(merge=merge, answer=turn.answer(latency)))
    return AgentReply(parts=turn.parts)


def _ending(record: SessionRecord, now: datetime) -> EndCall | None:
    if (now - record.started_at).total_seconds() >= record.max_duration_seconds:
        cut_by_quota = record.max_duration_seconds < MAX_SESSION_SECONDS
        return _end_call("quota" if cut_by_quota else "turns", record.language)
    if record.turn_count >= MAX_TURNS:
        return _end_call("turns", record.language)
    return None


def _end_call(reason: str, language: str) -> EndCall:
    return EndCall(reason=reason, message=phrase(END_CALL_REPLIES[reason], language))
