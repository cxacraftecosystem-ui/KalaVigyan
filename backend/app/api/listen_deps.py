from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import Depends, HTTPException, Request, status

from app.api.voice_deps import current_voice, voice_runtime
from app.core.db import sessionmaker
from app.core.deps import get_current_user, require
from app.core.errors import AppError
from app.core.roles import Capability, can, is_uncapped
from app.core.throttle_refusal import refuse_when_throttled
from app.models import User
from app.schemas.listen import ListenOffer
from app.services.object_store import media_bucket
from app.voice.languages import LISTEN_LANGUAGES
from app.voice.listen import Narrator
from app.voice.listen_store import SqlListenStore
from app.voice.narration_lease import LeasedObjects

__all__ = [
    "NO_LISTEN",
    "UNAVAILABLE_DETAIL",
    "ListenTools",
    "listen_store",
    "listen_tools",
    "offered_listen",
    "throttled_voice_user",
]

logger = logging.getLogger(__name__)

UNAVAILABLE_DETAIL = "Listening isn't available right now. Try again later."
NO_LISTEN: dict[str, Any] = {"languages": []}


@dataclass(frozen=True)
class ListenTools:
    objects: LeasedObjects
    narrator: Narrator
    voice_id: str


def throttled_voice_user(attempt: Callable[[str], tuple[bool, float]], detail: str) -> Callable[..., User]:
    def throttle(user: User = Depends(require(Capability.VOICE))) -> User:
        if not is_uncapped(user):
            refuse_when_throttled(attempt(str(user.id)), detail)
        return user

    return throttle


def listen_store() -> SqlListenStore:
    return SqlListenStore(sessionmaker())


async def listen_tools(request: Request) -> ListenTools:
    objects = media_bucket()
    voice = await current_voice()
    if objects is None or not voice.api_key:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, UNAVAILABLE_DETAIL)
    return ListenTools(
        objects=objects, narrator=voice_runtime(request).elevenlabs(voice), voice_id=voice.voice_id
    )


async def offered_listen(request: Request, user: User = Depends(get_current_user)) -> dict[str, Any]:
    if not can(user, Capability.VOICE) or media_bucket() is None:
        return dict(NO_LISTEN)
    try:
        voice = await current_voice()
        reachable = bool(voice.api_key) and await voice_runtime(request).reachable(voice)
    except AppError as error:
        logger.warning("listening could not be checked, Listen hidden: %s", error)
        return dict(NO_LISTEN)
    if not reachable:
        return dict(NO_LISTEN)
    return ListenOffer(languages=list(LISTEN_LANGUAGES)).model_dump(mode="json", by_alias=True)
