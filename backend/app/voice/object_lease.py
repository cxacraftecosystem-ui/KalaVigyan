from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Literal, Protocol

from pydantic import AwareDatetime, Field, ValidationError

from app.research.base import ContractModel

from .narration_cache import NarrationObjects

__all__ = [
    "LEASE_LEAF",
    "LEASE_SECONDS",
    "LEASE_WAIT_STEP_SECONDS",
    "LeaseTry",
    "LeasedObjects",
    "ObjectLease",
    "held_lease",
    "release_lease",
    "renew_lease",
    "take_lease",
    "waited",
]

logger = logging.getLogger(__name__)

LEASE_LEAF = "lease.json"
LEASE_TYPE = "application/json"
LEASE_SECONDS = 120
LEASE_WAIT_STEP_SECONDS = 1.0
Clock = Callable[[], datetime]
Sleep = Callable[[float], Awaitable[None]]


class LeasedObjects(NarrationObjects, Protocol):
    async def put_if_absent(self, key: str, body: bytes, *, content_type: str) -> bool: ...

    async def delete(self, key: str) -> None: ...


class ObjectLease(ContractModel):
    schema_version: Literal[1]
    cache_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    taken_at: AwareDatetime

    def lapses_at(self, seconds: float) -> datetime:
        return self.taken_at + timedelta(seconds=seconds)


@dataclass(frozen=True)
class LeaseTry:
    ours: bool
    lease: ObjectLease
    seconds: float

    @property
    def lapses_at(self) -> datetime:
        return self.lease.lapses_at(self.seconds)


async def take_lease(
    objects: LeasedObjects, key: str, cache_id: str, *, now: datetime, seconds: float = LEASE_SECONDS
) -> LeaseTry:
    lease = ObjectLease(schema_version=1, cache_id=cache_id, taken_at=now)
    body = _lease_body(lease)
    if await objects.put_if_absent(key, body, content_type=LEASE_TYPE):
        return LeaseTry(ours=True, lease=lease, seconds=seconds)
    held = await held_lease(objects, key)
    if held is not None and now < held.lapses_at(seconds):
        return LeaseTry(ours=False, lease=held, seconds=seconds)
    logger.warning("%s had a lapsed lease and is made by this request", key)
    await objects.put(key, body, content_type=LEASE_TYPE)
    return LeaseTry(ours=True, lease=lease, seconds=seconds)


async def waited[T](
    found: Callable[[], Awaitable[T | None]], held: LeaseTry, *, clock: Clock, sleep: Sleep
) -> T | None:
    for _ in range(round(held.seconds / LEASE_WAIT_STEP_SECONDS)):
        made = await found()
        if made is not None or clock() >= held.lapses_at:
            return made
        await sleep(LEASE_WAIT_STEP_SECONDS)
    return await found()


async def renew_lease(objects: LeasedObjects, key: str, cache_id: str, *, now: datetime) -> None:
    lease = ObjectLease(schema_version=1, cache_id=cache_id, taken_at=now)
    await objects.put(key, _lease_body(lease), content_type=LEASE_TYPE)


async def release_lease(objects: LeasedObjects, key: str) -> None:
    await objects.delete(key)


async def held_lease(objects: NarrationObjects, key: str) -> ObjectLease | None:
    raw = await objects.get(key)
    if raw is None:
        return None
    try:
        return ObjectLease.model_validate_json(raw)
    except ValidationError as error:
        logger.error("%s holds an unreadable lease, which is taken over: %s", key, error)
        return None


def _lease_body(lease: ObjectLease) -> bytes:
    return lease.model_dump_json(by_alias=True).encode("utf-8")
