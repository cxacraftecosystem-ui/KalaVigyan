from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, Protocol

from pydantic import AwareDatetime, Field, ValidationError

from app.research.base import ContractModel
from app.services.naming import narration_key

from .narration_cache import NarrationManifest, NarrationObjects, stored_manifest

__all__ = [
    "LEASE_LEAF",
    "LEASE_SECONDS",
    "LEASE_WAIT_STEP_SECONDS",
    "LeaseTry",
    "LeasedObjects",
    "NarrationLease",
    "release_lease",
    "take_lease",
    "waited_manifest",
]

logger = logging.getLogger(__name__)

LEASE_LEAF = "lease.json"
LEASE_TYPE = "application/json"
LEASE_SECONDS = 120
LEASE_WAIT_STEP_SECONDS = 1.0
LEASE_WAIT_STEPS = round(LEASE_SECONDS / LEASE_WAIT_STEP_SECONDS)
Clock = Callable[[], datetime]
Sleep = Callable[[float], Awaitable[None]]


class LeasedObjects(NarrationObjects, Protocol):
    async def put_if_absent(self, key: str, body: bytes, *, content_type: str) -> bool: ...

    async def delete(self, key: str) -> None: ...


class NarrationLease(ContractModel):
    schema_version: Literal[1]
    cache_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    taken_at: AwareDatetime

    def lapses_at(self) -> datetime:
        return self.taken_at + timedelta(seconds=LEASE_SECONDS)


@dataclass(frozen=True)
class LeaseTry:
    ours: bool
    lease: NarrationLease


async def take_lease(objects: LeasedObjects, cache_id: str, *, now: datetime) -> LeaseTry:
    lease = NarrationLease(schema_version=1, cache_id=cache_id, taken_at=now)
    body = lease.model_dump_json(by_alias=True).encode("utf-8")
    key = narration_key(cache_id, LEASE_LEAF)
    if await objects.put_if_absent(key, body, content_type=LEASE_TYPE):
        return LeaseTry(ours=True, lease=lease)
    held = await _held_lease(objects, cache_id)
    if held is not None and now < held.lapses_at():
        return LeaseTry(ours=False, lease=held)
    logger.warning("narration %s had a lapsed lease and is made by this request", cache_id)
    await objects.put(key, body, content_type=LEASE_TYPE)
    return LeaseTry(ours=True, lease=lease)


async def waited_manifest(
    objects: NarrationObjects, held: NarrationLease, *, clock: Clock, sleep: Sleep
) -> NarrationManifest | None:
    for _ in range(LEASE_WAIT_STEPS):
        found = await stored_manifest(objects, held.cache_id)
        if found is not None or clock() >= held.lapses_at():
            return found
        await sleep(LEASE_WAIT_STEP_SECONDS)
    return await stored_manifest(objects, held.cache_id)


async def release_lease(objects: LeasedObjects, cache_id: str) -> None:
    await objects.delete(narration_key(cache_id, LEASE_LEAF))


async def _held_lease(objects: NarrationObjects, cache_id: str) -> NarrationLease | None:
    raw = await objects.get(narration_key(cache_id, LEASE_LEAF))
    if raw is None:
        return None
    try:
        return NarrationLease.model_validate_json(raw)
    except ValidationError as error:
        logger.error("narration %s holds an unreadable lease, which is taken over: %s", cache_id, error)
        return None
