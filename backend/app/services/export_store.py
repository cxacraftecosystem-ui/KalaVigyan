from __future__ import annotations

import asyncio
import hashlib
import json
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from app.research.export_links import (
    EXPORT_LINK_SCHEMA_VERSION,
    EXPORT_LINK_SECONDS,
    EXPORT_MEDIA_TYPES,
    ExportLink,
)

from .naming import content_disposition, export_key
from .object_store import PresignedGet

__all__ = [
    "EXPORT_BUILDS_AT_ONCE",
    "EXPORT_RENDERING",
    "BuiltExport",
    "ExportFile",
    "ExportObjects",
    "export_digest",
    "stored_export_link",
]

EXPORT_RENDERING = "kalavigyan-export/v1"
EXPORT_BUILDS_AT_ONCE = 2


class ExportObjects(Protocol):
    async def exists(self, key: str) -> bool: ...

    async def put(self, key: str, body: bytes, *, content_type: str) -> None: ...

    def presigned_get(self, key: str, *, disposition: str, seconds: int, now: datetime) -> PresignedGet: ...


@dataclass(frozen=True)
class ExportFile:
    owner_id: uuid.UUID
    fmt: str
    file_name: str
    made_from: Any

    def key(self) -> str:
        return export_key(self.owner_id, export_digest(self.fmt, self.made_from), self.file_name)

    def key_without(self, unread: frozenset[uuid.UUID]) -> str:
        made_from = {"madeFrom": self.made_from, "unread": sorted(str(one) for one in unread)}
        return export_key(self.owner_id, export_digest(self.fmt, made_from), self.file_name)


@dataclass(frozen=True)
class BuiltExport:
    body: bytes
    unread: frozenset[uuid.UUID] = frozenset()


def export_digest(fmt: str, made_from: Any) -> str:
    canonical = json.dumps(
        [EXPORT_RENDERING, fmt, made_from], sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


async def stored_export_link(
    objects: ExportObjects,
    export: ExportFile,
    build: Callable[[], Awaitable[BuiltExport]],
    *,
    now: datetime,
    builds: asyncio.Semaphore,
) -> ExportLink:
    key = export.key()
    if not await objects.exists(key):
        key = await _filed(objects, export, build, builds)
    link = objects.presigned_get(
        key,
        disposition=content_disposition(export.file_name, inline=False),
        seconds=EXPORT_LINK_SECONDS,
        now=now,
    )
    return ExportLink(
        schema_version=EXPORT_LINK_SCHEMA_VERSION,
        format=export.fmt,
        file_name=export.file_name,
        url=link.url,
        expires_at=link.expires_at,
    )


async def _filed(
    objects: ExportObjects,
    export: ExportFile,
    build: Callable[[], Awaitable[BuiltExport]],
    builds: asyncio.Semaphore,
) -> str:
    key = export.key()
    async with builds:
        if await objects.exists(key):
            return key
        built = await build()
        if built.unread:
            key = export.key_without(built.unread)
        await objects.put(key, built.body, content_type=EXPORT_MEDIA_TYPES[export.fmt])
    return key
