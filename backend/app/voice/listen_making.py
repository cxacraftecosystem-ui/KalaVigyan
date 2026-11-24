from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable
from dataclasses import replace
from datetime import datetime
from functools import partial

from app.core.errors import AppError
from app.providers.quota import seconds_until_next_day
from app.services.naming import narration_file_name, narration_key

from .listen_ask import ListenAsk, ListenDeps, ListenHold, ListenLedger, ListenRefused
from .listen_voices import ListenVoice
from .narration import NarrationPart, SpokenBlock, estimated_seconds, narration_parts
from .narration_cache import NarratedPart, NarrationManifest, store_manifest, stored_manifest
from .object_lease import (
    LEASE_LEAF,
    LEASE_SECONDS,
    LeasedObjects,
    LeaseTry,
    release_lease,
    renew_lease,
    take_lease,
    waited,
)
from .seconds import capped_seconds, listen_hold_key, listen_refund_key, listen_settle_key

__all__ = [
    "BUSY_MESSAGE",
    "LEASE_RENEW_SECONDS",
    "LISTEN_CONCURRENCY",
    "QUOTA_MESSAGE",
    "first_block_made",
]

logger = logging.getLogger(__name__)

LISTEN_CONCURRENCY = 3
LEASE_RENEW_SECONDS = LEASE_SECONDS / 4
QUOTA_MESSAGE = "Not enough listening time is left today."
BUSY_MESSAGE = "The audio is still being prepared. Try again in a minute."


async def first_block_made(
    ask: ListenAsk, deps: ListenDeps, voice: ListenVoice, missing: dict[str, SpokenBlock], first: str
) -> dict[str, NarrationManifest]:
    found: dict[str, NarrationManifest] = {}
    ours: dict[str, SpokenBlock] = {}
    if first in missing:
        made = await _first_made_elsewhere(deps, first)
        if made is None:
            ours[first] = missing[first]
        else:
            found[first] = made
    rest = [cache_id for cache_id in missing if cache_id != first]
    tries = await asyncio.gather(*(_lease(deps, cache_id) for cache_id in rest))
    ours |= {cache_id: missing[cache_id] for cache_id, tried in zip(rest, tries, strict=True) if tried.ours}
    if not ours:
        return found
    making = await _Making.started(ask, deps, voice, ours)
    if first in ours:
        found[first] = await making.made(first)
    return found


async def _first_made_elsewhere(deps: ListenDeps, first: str) -> NarrationManifest | None:
    tried = await _lease(deps, first)
    if tried.ours:
        return None
    made = await _waited(deps, tried)
    if made is not None or (await _lease(deps, first)).ours:
        return made
    raise ListenRefused("busy", BUSY_MESSAGE)


class _Making:
    def __init__(self, ask: ListenAsk, deps: ListenDeps, voice: ListenVoice, ours: dict[str, SpokenBlock]):
        self._ask, self._deps, self._voice, self._ours = ask, deps, voice, ours
        self._gate = asyncio.Semaphore(LISTEN_CONCURRENCY)
        self._seconds = 0
        self._open = set(ours)
        self._tasks: dict[str, asyncio.Task[NarrationManifest]] = {}
        self._settled = asyncio.Event()

    @classmethod
    async def started(
        cls, ask: ListenAsk, deps: ListenDeps, voice: ListenVoice, ours: dict[str, SpokenBlock]
    ) -> _Making:
        making = cls(ask, deps, voice, ours)
        try:
            await deps.admit()
            hold = await making._held()
        except BaseException:
            await _released(deps.objects, ours)
            raise
        making._tasks = {
            cache_id: asyncio.create_task(making._block(cache_id, block)) for cache_id, block in ours.items()
        }
        name = f"narration of answer {ask.explainer.answer_id} by {voice.name}"
        deps.shield.start(making._finished(hold), name=name)
        return making

    async def made(self, cache_id: str) -> NarrationManifest:
        try:
            return await asyncio.shield(self._tasks[cache_id])
        except Exception:
            for task in self._tasks.values():
                task.cancel()
            await self._settled.wait()
            raise

    async def _held(self) -> ListenHold:
        characters = sum(len(part.text) for block in self._ours.values() for part in narration_parts(block))
        now = self._deps.clock()
        key = listen_hold_key(self._ask.request_id, self._voice.service)
        entry = self._ask.entry(estimated_seconds(characters), key, counted_at=now)
        hold = await self._deps.ledger.hold(entry, now)
        if hold.refused:
            raise ListenRefused("quota", QUOTA_MESSAGE, retry_after=seconds_until_next_day(now))
        return replace(hold, counted_at=now)

    async def _finished(self, hold: ListenHold) -> None:
        keeper = asyncio.create_task(self._kept_alive())
        try:
            outcomes = await asyncio.gather(*self._tasks.values(), return_exceptions=True)
        finally:
            keeper.cancel()
            await asyncio.gather(keeper, return_exceptions=True)
            try:
                await _settled(self._ask, self._deps.ledger, hold, self._seconds, self._voice.service)
            finally:
                self._settled.set()
        for cache_id, outcome in zip(self._tasks, outcomes, strict=True):
            if isinstance(outcome, Exception):
                logger.warning("the narration %s by %s was not made: %s", cache_id, self._voice.name, outcome)

    async def _kept_alive(self) -> None:
        while True:
            await asyncio.sleep(LEASE_RENEW_SECONDS)
            now = self._deps.clock()
            for cache_id in list(self._open):
                await self._renewed(cache_id, now)

    async def _renewed(self, cache_id: str, now: datetime) -> None:
        if cache_id not in self._open:
            return
        try:
            await renew_lease(self._deps.objects, _lease_key(cache_id), cache_id, now=now)
        except AppError as error:
            logger.warning("the lease on narration %s was not renewed: %s", cache_id, error)

    async def _block(self, cache_id: str, block: SpokenBlock) -> NarrationManifest:
        try:
            parts = narration_parts(block)
            made = [await self._part(cache_id, parts, index) for index in range(len(parts))]
            manifest = NarrationManifest(
                schema_version=1,
                cache_id=cache_id,
                model=self._voice.model,
                voice_id=self._voice.voice_id,
                language=self._ask.language,
                content_hash=block.content_hash,
                parts=made,
            )
            await store_manifest(self._deps.objects, manifest)
            return manifest
        finally:
            self._open.discard(cache_id)
            await _released(self._deps.objects, [cache_id])

    async def _part(self, cache_id: str, parts: list[NarrationPart], index: int) -> NarratedPart:
        async with self._gate:
            spoken = await self._voice.spoken(parts, index)
        self._seconds += spoken.billed_seconds
        leaf = narration_file_name(self._deps.clock(), index + 1, ext=self._voice.extension)
        key = narration_key(cache_id, leaf)
        await self._deps.objects.put(key, spoken.audio, content_type=self._voice.audio_type)
        return NarratedPart(
            key=key,
            language=parts[index].language,
            duration_seconds=spoken.duration_seconds,
            words=spoken.words,
            sentences=spoken.sentences,
        )


async def _lease(deps: ListenDeps, cache_id: str) -> LeaseTry:
    return await take_lease(deps.objects, _lease_key(cache_id), cache_id, now=deps.clock())


async def _waited(deps: ListenDeps, held: LeaseTry) -> NarrationManifest | None:
    found = partial(stored_manifest, deps.objects, held.lease.cache_id)
    return await waited(found, held, clock=deps.clock, sleep=deps.sleep)


def _lease_key(cache_id: str) -> str:
    return narration_key(cache_id, LEASE_LEAF)


async def _released(objects: LeasedObjects, cache_ids: Iterable[str]) -> None:
    for cache_id in cache_ids:
        try:
            await release_lease(objects, _lease_key(cache_id))
        except AppError as error:
            logger.warning("the lease on narration %s lapses on its own: %s", cache_id, error)


async def _settled(ask: ListenAsk, ledger: ListenLedger, hold: ListenHold, billed: int, voice: str) -> None:
    unused = hold.held - billed
    if unused > 0:
        key = listen_refund_key(ask.request_id, voice)
        await ledger.record(ask.entry(-unused, key, counted_at=hold.counted_at))
    elif unused < 0:
        extra = capped_seconds(-unused, hold.remaining_after)
        if extra:
            key = listen_settle_key(ask.request_id, voice)
            await ledger.record(ask.entry(extra, key, counted_at=hold.counted_at))
