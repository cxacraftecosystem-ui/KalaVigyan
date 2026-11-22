from __future__ import annotations

import hashlib
import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.errors import ExternalFailure, NotConfigured
from app.core.security import secret_key_or_none
from app.providers.elevenlabs import ELEVENLABS_KEY_NAME, ElevenLabs
from app.research.retrieval import KnowledgeRetriever
from app.schemas.voice import VOICE_TRANSPORTS
from app.services import app_settings, managed_secrets
from app.services.object_store import media_bucket

from .audio_decode import Measure, decoded_seconds
from .binding import HMAC_KEY_NAME
from .pack import VoicePackStore
from .privacy import TranscriptCipher, transcript_cipher
from .reply_audio import ReplyAudio, ReplyObjects

__all__ = [
    "BEARER_MIN_CHARS",
    "REACHABILITY_TTL_SECONDS",
    "VoiceRuntime",
    "VoiceSettings",
    "voice_settings",
]

logger = logging.getLogger(__name__)

BEARER_MIN_CHARS = 32
REACHABILITY_TTL_SECONDS = 60.0
SearchFor = Callable[[uuid.UUID, str], KnowledgeRetriever]


@dataclass(frozen=True)
class VoiceSettings:
    transport: str | None
    max_live_sessions: int
    voice_id: str
    api_key: str | None
    agent_id: str | None
    llm_bearer: str | None
    hmac_key: bytes | None
    cipher: TranscriptCipher | None

    def missing(self) -> list[str]:
        needed = {
            "voice.transport": self.transport is not None,
            ELEVENLABS_KEY_NAME: bool(self.api_key),
            "TRANSCRIPT_ENCRYPTION_KEY": self.cipher is not None,
        }
        if self.transport == "AGENT":
            needed |= {
                "ELEVENLABS_AGENT_ID": bool(self.agent_id),
                "VOICE_LLM_BEARER": len(self.llm_bearer or "") >= BEARER_MIN_CHARS,
                "VOICE_SESSION_HMAC_KEY": self.hmac_key is not None,
            }
        return [name for name, present in needed.items() if not present]


async def voice_settings(session: AsyncSession, settings: Settings) -> VoiceSettings:
    values = await app_settings.load_all(session)
    transport = values[app_settings.VOICE_TRANSPORT]
    if transport not in VOICE_TRANSPORTS:
        logger.error(
            "AppSetting %s is %r, not one of %s", app_settings.VOICE_TRANSPORT, transport, VOICE_TRANSPORTS
        )
        transport = None
    return VoiceSettings(
        transport=transport,
        max_live_sessions=max(0, int(values[app_settings.VOICE_MAX_LIVE_SESSIONS])),
        voice_id=str(values[app_settings.VOICE_VOICE_ID]),
        api_key=await managed_secrets.get_secret(session, ELEVENLABS_KEY_NAME),
        agent_id=(settings.elevenlabs_agent_id or "").strip() or None,
        llm_bearer=(settings.voice_llm_bearer or "").strip() or None,
        hmac_key=secret_key_or_none(HMAC_KEY_NAME, settings.voice_session_hmac_key),
        cipher=_cipher_or_none(settings.transcript_encryption_key),
    )


def _cipher_or_none(value: str | None) -> TranscriptCipher | None:
    try:
        return transcript_cipher(value)
    except NotConfigured as missing:
        if (value or "").strip():
            logger.error("%s is set but unusable", missing.name)
        return None


class VoiceRuntime:
    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        objects: ReplyObjects | None = None,
        measure: Measure = decoded_seconds,
        search: SearchFor | None = None,
    ) -> None:
        self.client = client or httpx.AsyncClient(follow_redirects=False)
        self.packs = VoicePackStore()
        self.measure = measure
        self._search = search
        self._objects = objects
        self._reachable: tuple[float, str, bool] | None = None

    def stored_search(self, user_id: uuid.UUID, role: str) -> KnowledgeRetriever | None:
        return None if self._search is None else self._search(user_id, role)

    def replies(self) -> ReplyAudio:
        return ReplyAudio(self._objects or media_bucket())

    def elevenlabs(self, voice: VoiceSettings) -> ElevenLabs:
        if not voice.api_key:
            raise NotConfigured(ELEVENLABS_KEY_NAME, f"{ELEVENLABS_KEY_NAME} is not set")
        return ElevenLabs(api_key=voice.api_key, client=self.client)

    async def reachable(self, voice: VoiceSettings) -> bool:
        fingerprint = hashlib.sha256((voice.api_key or "").encode("utf-8")).hexdigest()
        now = time.monotonic()
        if (
            self._reachable
            and self._reachable[1] == fingerprint
            and now - self._reachable[0] < REACHABILITY_TTL_SECONDS
        ):
            return self._reachable[2]
        try:
            await self.elevenlabs(voice).account()
            answer = True
        except (ExternalFailure, NotConfigured) as error:
            logger.warning("ElevenLabs is not reachable: %s", error)
            answer = False
        self._reachable = (now, fingerprint, answer)
        return answer

    async def aclose(self) -> None:
        await self.client.aclose()
