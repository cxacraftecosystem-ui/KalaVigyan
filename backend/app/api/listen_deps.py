from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, Request, status

from app.api.voice_deps import current_voice, voice_runtime
from app.core.db import sessionmaker
from app.core.deps import get_current_user
from app.core.errors import AppError
from app.core.managed_keys import get_secret
from app.core.rate_limit import listen_attempt
from app.core.roles import Capability, can, is_uncapped
from app.core.throttle_refusal import refuse_when_throttled
from app.models import User
from app.providers.gemini_media import GEMINI_KEY_NAME, GeminiMediaWire
from app.services.object_store import media_bucket
from app.voice.listen_ask import Admission
from app.voice.listen_store import SqlListenStore
from app.voice.listen_voices import ElevenLabsVoice, GeminiVoice, ListenVoice, listen_offer
from app.voice.object_lease import LeasedObjects

__all__ = [
    "NO_LISTEN",
    "THROTTLED_DETAIL",
    "UNAVAILABLE_DETAIL",
    "ListenTools",
    "listen_store",
    "listen_tools",
    "listen_voices",
    "making_admission",
    "offered_listen",
    "read_aloud_key",
]

logger = logging.getLogger(__name__)

UNAVAILABLE_DETAIL = "Listening isn't available right now. Try again later."
THROTTLED_DETAIL = "You have pressed Listen many times in a few minutes. Wait a little and try again."
NO_LISTEN: dict[str, Any] = {"languages": []}


@dataclass(frozen=True)
class ListenTools:
    objects: LeasedObjects
    voices: tuple[ListenVoice, ...]


def making_admission(user: User) -> Admission:
    async def admitted() -> None:
        if not is_uncapped(user):
            refuse_when_throttled(await listen_attempt(str(user.id)), THROTTLED_DETAIL)

    return admitted


def listen_store() -> SqlListenStore:
    return SqlListenStore(sessionmaker())


async def listen_tools(request: Request) -> ListenTools:
    objects = media_bucket()
    voices = await listen_voices(request) if objects is not None else ()
    if objects is None or not voices:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, UNAVAILABLE_DETAIL)
    return ListenTools(objects=objects, voices=voices)


async def listen_voices(request: Request) -> tuple[ListenVoice, ...]:
    runtime = voice_runtime(request)
    voice = await current_voice()
    found: list[ListenVoice] = []
    if voice.api_key and await runtime.reachable(voice):
        found.append(ElevenLabsVoice(narrator=runtime.elevenlabs(voice), voice_id=voice.voice_id))
    key = await read_aloud_key()
    if key:
        found.append(GeminiVoice(reader=GeminiMediaWire(api_key=key, client=runtime.client)))
    return tuple(found)


async def read_aloud_key() -> str | None:
    async with sessionmaker()() as session:
        return await get_secret(session, GEMINI_KEY_NAME)


async def offered_listen(request: Request, user: User = Depends(get_current_user)) -> dict[str, Any]:
    if not can(user, Capability.VOICE) or media_bucket() is None:
        return dict(NO_LISTEN)
    try:
        voices = await listen_voices(request)
    except AppError as error:
        logger.warning("listening could not be checked, Listen hidden: %s", error)
        return dict(NO_LISTEN)
    return listen_offer(voices).model_dump(mode="json", by_alias=True)
