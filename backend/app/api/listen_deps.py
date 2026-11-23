from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, Request, status

from app.api.voice_deps import current_voice, voice_runtime
from app.core.db import sessionmaker
from app.core.deps import get_current_user, require
from app.core.errors import AppError
from app.core.managed_keys import get_secret
from app.core.roles import Capability, can, is_uncapped
from app.core.throttle_refusal import refuse_when_throttled
from app.models import User
from app.providers.gemini_media import GEMINI_KEY_NAME, GeminiMediaWire
from app.services.object_store import media_bucket
from app.voice.listen_store import SqlListenStore
from app.voice.listen_voices import ElevenLabsVoice, GeminiVoice, ListenVoice, listen_offer
from app.voice.object_lease import LeasedObjects

__all__ = [
    "NO_LISTEN",
    "UNAVAILABLE_DETAIL",
    "ListenTools",
    "listen_store",
    "listen_tools",
    "listen_voices",
    "offered_listen",
    "read_aloud_key",
    "throttled_voice_user",
]

logger = logging.getLogger(__name__)

UNAVAILABLE_DETAIL = "Listening isn't available right now. Try again later."
NO_LISTEN: dict[str, Any] = {"languages": []}


@dataclass(frozen=True)
class ListenTools:
    objects: LeasedObjects
    voices: tuple[ListenVoice, ...]


def throttled_voice_user(
    attempt: Callable[[str], Awaitable[tuple[bool, float]]], detail: str
) -> Callable[..., Awaitable[User]]:
    async def throttle(user: User = Depends(require(Capability.VOICE))) -> User:
        if not is_uncapped(user):
            refuse_when_throttled(await attempt(str(user.id)), detail)
        return user

    return throttle


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
