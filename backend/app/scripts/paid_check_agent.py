from __future__ import annotations

import json
import uuid
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import httpx
from sqlalchemy import select
from websockets.exceptions import WebSocketException

from app.core.config import Settings
from app.core.db import session_scope, sessionmaker
from app.core.errors import AppError
from app.models import User
from app.providers.elevenlabs import ElevenLabs
from app.providers.elevenlabs_socket import SocketTurn, one_turn, signed_conversation_url
from app.voice.binding import nonce_hash, session_nonce
from app.voice.records import SessionRecord
from app.voice.runtime import VoiceSettings, voice_settings
from app.voice.seconds import START_WINDOW_SECONDS
from app.voice.store import SqlVoiceStore

from .paid_check_steps import CheckResult

__all__ = ["AGENT_QUESTION", "AGENT_TURN_USD", "agent_check", "turn_findings"]

AGENT_TURN_USD = Decimal("1.50")
AGENT_QUESTION = "What is Ajrakh?"
AGENT_MODE = "HYBRID"
AGENT_TRANSPORT = "AGENT"
AGENT_SESSION_SECONDS = 180


async def agent_check(client: httpx.AsyncClient, settings: Settings) -> CheckResult:
    async with session_scope() as session:
        voice = await voice_settings(session, settings)
        admin = await session.scalar(select(User).where(User.email == settings.master_admin_email))
    if admin is None or not (voice.api_key and voice.agent_id and voice.hmac_key):
        return CheckResult({"refused": "the agent, its key, the session key or the Master Admin is missing"})
    url = await signed_conversation_url(client, api_key=voice.api_key, agent_id=voice.agent_id)
    store = SqlVoiceStore(sessionmaker())
    record = _session(admin)
    if not await store.create(record):
        return CheckResult({"refused": "the Master Admin already has a live voice session"})
    try:
        turn = await one_turn(url, AGENT_QUESTION, bind=_binder(store, record, voice))
    except (WebSocketException, OSError) as error:
        return CheckResult({"refused": f"the conversation socket failed: {type(error).__name__}"})
    finally:
        await store.end(record.id, datetime.now(UTC))
    deleted = await _forgotten(client, voice, turn)
    events = (json.dumps(turn.events, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    return CheckResult(
        turn_findings(turn) | {"conversationDeleted": deleted}, {"agent_turn_events.json": events}
    )


def turn_findings(turn: SocketTurn) -> dict[str, object]:
    return {
        "question": AGENT_QUESTION,
        "conversationStarted": turn.conversation_id is not None,
        "replies": turn.replies,
        "events": dict(Counter(str(event.get("type")) for event in turn.events)),
    }


def _session(admin: User) -> SessionRecord:
    now = datetime.now(UTC)
    return SessionRecord(
        id=uuid.uuid4(),
        user_id=admin.id,
        role=admin.role,
        craft=None,
        mode=AGENT_MODE,
        language="en",
        transport=AGENT_TRANSPORT,
        started_at=now,
        expires_at=now + timedelta(seconds=START_WINDOW_SECONDS),
        max_duration_seconds=AGENT_SESSION_SECONDS,
        chat_id=uuid.uuid4(),
    )


def _binder(
    store: SqlVoiceStore, record: SessionRecord, voice: VoiceSettings
) -> Callable[[str], Awaitable[None]]:
    async def bind(conversation_id: str) -> None:
        bound = replace(record, conversation_id=conversation_id)
        hashed = nonce_hash(session_nonce(voice.hmac_key or b"", bound, conversation_id))
        await store.bind(
            record.id, conversation_id=conversation_id, agent_id=voice.agent_id or "", nonce_hash=hashed
        )

    return bind


async def _forgotten(client: httpx.AsyncClient, voice: VoiceSettings, turn: SocketTurn) -> str:
    if turn.conversation_id is None or not voice.api_key:
        return "no conversation"
    try:
        await ElevenLabs(api_key=voice.api_key, client=client).delete_conversation(turn.conversation_id)
    except AppError as error:
        return f"not deleted: {error}"
    return "deleted"
