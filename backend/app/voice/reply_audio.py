from __future__ import annotations

import logging
import uuid
from typing import Protocol

from app.core.errors import AppError
from app.services.naming import voice_reply_key

__all__ = ["REPLY_TYPE", "ReplyAudio", "ReplyObjects"]

logger = logging.getLogger(__name__)

REPLY_TYPE = "audio/mpeg"


class ReplyObjects(Protocol):
    async def get(self, key: str) -> bytes | None: ...

    async def put(self, key: str, body: bytes, *, content_type: str) -> None: ...


class ReplyAudio:
    def __init__(self, objects: ReplyObjects | None) -> None:
        self._objects = objects

    async def put(self, session_id: uuid.UUID, turn_id: uuid.UUID, audio: bytes) -> None:
        if self._objects is None:
            logger.error("no media bucket keeps reply %s, so its speech route makes it again", turn_id)
            return
        try:
            await self._objects.put(voice_reply_key(session_id, turn_id), audio, content_type=REPLY_TYPE)
        except AppError as error:
            logger.warning("reply %s was not kept, so its speech route makes it again: %s", turn_id, error)

    async def get(self, session_id: uuid.UUID, turn_id: uuid.UUID) -> bytes | None:
        if self._objects is None:
            return None
        return await self._objects.get(voice_reply_key(session_id, turn_id))
