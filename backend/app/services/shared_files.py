from __future__ import annotations

import logging
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol

from sqlalchemy import ColumnElement, delete, exists, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ExternalFailure, InvalidInput
from app.models import Answer, LessonPack, SharedExportFile

from .export_store import ExportObjects
from .naming import EXPORTS_PREFIX
from .object_store import PresignedGet

__all__ = [
    "SHARED_EXPORT_OWNER",
    "SHARED_FILES_PER_SWEEP",
    "DroppedFiles",
    "FileDeleter",
    "SignedKeys",
    "drop_stopped_share_files",
    "record_shared_files",
]

SHARED_EXPORT_OWNER = uuid.UUID(int=0)
SHARED_PREFIX = f"{EXPORTS_PREFIX}/{SHARED_EXPORT_OWNER}/"
SHARED_FILES_PER_SWEEP = 200

logger = logging.getLogger(__name__)


class FileDeleter(Protocol):
    async def delete(self, key: str) -> None: ...


@dataclass(frozen=True)
class DroppedFiles:
    dropped: int
    kept: int


@dataclass
class SignedKeys:
    objects: ExportObjects
    keys: list[str] = field(default_factory=list)

    async def exists(self, key: str) -> bool:
        return await self.objects.exists(key)

    async def put(self, key: str, body: bytes, *, content_type: str) -> None:
        await self.objects.put(key, body, content_type=content_type)

    async def delete(self, key: str) -> None:
        await self.objects.delete(key)

    def presigned_get(self, key: str, *, disposition: str, seconds: int, now: datetime) -> PresignedGet:
        self.keys.append(key)
        return self.objects.presigned_get(key, disposition=disposition, seconds=seconds, now=now)


async def record_shared_files(
    session: AsyncSession, token: str, keys: Iterable[str], *, objects: FileDeleter
) -> DroppedFiles:
    named = list(dict.fromkeys(keys))
    outside = [key for key in named if not key.startswith(SHARED_PREFIX)]
    if outside:
        raise InvalidInput(f"A shared file is filed under {SHARED_PREFIX}, not {outside[0]}")
    if not named:
        return DroppedFiles(dropped=0, kept=0)
    statement = insert(SharedExportFile).values([{"key": key, "shareToken": token} for key in named])
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=[SharedExportFile.key], set_={"shareToken": statement.excluded.shareToken}
        )
    )
    held = await session.scalar(select(~_held_by_no_share(token)))
    dropped = DroppedFiles(dropped=0, kept=0) if held else await _drop(session, objects, named)
    await session.commit()
    return dropped


async def drop_stopped_share_files(session: AsyncSession, objects: FileDeleter | None) -> DroppedFiles:
    if objects is None:
        return DroppedFiles(dropped=0, kept=0)
    stopped = await session.execute(
        select(SharedExportFile.key)
        .where(_held_by_no_share(SharedExportFile.shareToken))
        .order_by(SharedExportFile.createdAt)
        .limit(SHARED_FILES_PER_SWEEP)
        .with_for_update(skip_locked=True)
    )
    return await _drop(session, objects, list(stopped.scalars().all()))


async def _drop(session: AsyncSession, objects: FileDeleter, keys: Sequence[str]) -> DroppedFiles:
    dropped: list[str] = []
    failures: list[ExternalFailure] = []
    for key in keys:
        try:
            await objects.delete(key)
        except ExternalFailure as failure:
            failures.append(failure)
            continue
        dropped.append(key)
    if dropped:
        await session.execute(delete(SharedExportFile).where(SharedExportFile.key.in_(dropped)))
    if failures:
        logger.warning(
            "%s files of stopped shares are kept for the next sweep: %s", len(failures), failures[0]
        )
    return DroppedFiles(dropped=len(dropped), kept=len(failures))


def _held_by_no_share(token: Any) -> ColumnElement[bool]:
    return ~exists().where(Answer.shareToken == token) & ~exists().where(LessonPack.shareToken == token)
