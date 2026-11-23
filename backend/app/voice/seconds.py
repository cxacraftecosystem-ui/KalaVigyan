from __future__ import annotations

import uuid

from app.providers.quota import LedgerEntry
from app.schemas.voice import MAX_SESSION_SECONDS

from .records import SessionRecord

__all__ = [
    "AGENT_OCCUPANCY_SECONDS",
    "LEDGER_REF_TYPE",
    "START_WINDOW_SECONDS",
    "VOICE_SECONDS",
    "agent_hold_key",
    "capped_seconds",
    "ledger_entry",
    "listen_hold_key",
    "listen_refund_key",
    "listen_settle_key",
    "refund_key",
    "relay_audio_key",
    "relay_refund_key",
    "relay_replay_key",
    "relay_speech_key",
    "settle_key",
    "time_left",
]

VOICE_SECONDS = "VOICE_SECONDS"
LEDGER_REF_TYPE = "VoiceSession"
START_WINDOW_SECONDS = 120
AGENT_OCCUPANCY_SECONDS = START_WINDOW_SECONDS + MAX_SESSION_SECONDS


def agent_hold_key(session_id: uuid.UUID) -> str:
    return f"voice:{session_id}:hold"


def relay_audio_key(session_id: uuid.UUID, turn_id: uuid.UUID) -> str:
    return f"voice:{session_id}:{turn_id}"


def relay_speech_key(session_id: uuid.UUID, turn_id: uuid.UUID) -> str:
    return f"voice:{session_id}:{turn_id}:speech"


def relay_replay_key(session_id: uuid.UUID, turn_id: uuid.UUID, replay_id: uuid.UUID) -> str:
    return f"voice:{session_id}:{turn_id}:speech:{replay_id.hex}"


def relay_refund_key(session_id: uuid.UUID, turn_id: uuid.UUID) -> str:
    return f"voice-refund:{session_id}:{turn_id}"


def refund_key(session_id: uuid.UUID) -> str:
    return f"voice-refund:{session_id}"


def settle_key(session_id: uuid.UUID) -> str:
    return f"voice-settle:{session_id}"


def listen_hold_key(request_id: uuid.UUID, voice: str) -> str:
    return f"listen:{request_id}:{voice}:hold"


def listen_refund_key(request_id: uuid.UUID, voice: str) -> str:
    return f"listen-refund:{request_id}:{voice}"


def listen_settle_key(request_id: uuid.UUID, voice: str) -> str:
    return f"listen-settle:{request_id}:{voice}"


def capped_seconds(charge: int, remaining: int | None) -> int:
    return charge if remaining is None else max(0, min(charge, remaining))


def time_left(remaining: int | None, charged: int) -> int | None:
    return None if remaining is None else max(0, remaining - charged)


def ledger_entry(record: SessionRecord, *, units: int, key: str) -> LedgerEntry:
    return LedgerEntry(
        user_id=record.user_id,
        resource=VOICE_SECONDS,
        units=units,
        key=key,
        ref_type=LEDGER_REF_TYPE,
        ref_id=str(record.id),
    )
