from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass, field
from datetime import datetime
from functools import partial
from typing import Protocol

from app.core.errors import AppError, Refused
from app.providers.elevenlabs import NARRATION_MODEL, TimedSpeech, speech_seconds
from app.providers.quota import LedgerEntry, seconds_until_next_day
from app.research.explainer import Explainer
from app.schemas.listen import LISTEN_SCHEMA_VERSION, ListenScript, ListenTrack
from app.services.naming import content_disposition, narration_file_name, narration_key

from .narration import (
    NarrationPart,
    SpokenBlock,
    estimated_seconds,
    narration_cache_id,
    narration_parts,
    part_duration,
    part_words,
    spoken_blocks,
)
from .narration_cache import (
    AUDIO_TYPE,
    NarratedPart,
    NarrationManifest,
    NarrationObjects,
    store_manifest,
    stored_manifest,
)
from .object_lease import LEASE_LEAF, LeasedObjects, LeaseTry, release_lease, take_lease, waited
from .seconds import VOICE_SECONDS, capped_seconds, listen_hold_key, listen_refund_key, listen_settle_key

__all__ = [
    "LISTEN_CONCURRENCY",
    "LISTEN_LEDGER_REF",
    "NARRATION_LINK_SECONDS",
    "NOTHING_MESSAGE",
    "ListenAsk",
    "ListenDeps",
    "ListenHold",
    "ListenLedger",
    "ListenRefused",
    "Narrator",
    "listen_script",
]

logger = logging.getLogger(__name__)

LISTEN_CONCURRENCY = 3
NARRATION_LINK_SECONDS = 3600
LISTEN_LEDGER_REF = "Answer"
QUOTA_MESSAGE = "Not enough listening time is left today."
NOTHING_MESSAGE = "There is nothing to read aloud here."


class ListenRefused(Refused):
    def __init__(self, reason: str, message: str, *, retry_after: int | None = None) -> None:
        super().__init__(reason, message)
        self.retry_after = retry_after


@dataclass(frozen=True)
class ListenHold:
    held: int
    remaining_after: int | None
    refused: bool = False


class ListenLedger(Protocol):
    async def hold(self, entry: LedgerEntry, now: datetime) -> ListenHold: ...

    async def record(self, entry: LedgerEntry) -> None: ...


class Narrator(Protocol):
    async def narration(
        self, text: str, *, voice_id: str, language: str, previous_text: str = "", next_text: str = ""
    ) -> TimedSpeech: ...


@dataclass(frozen=True)
class ListenDeps:
    ledger: ListenLedger
    objects: LeasedObjects
    narrator: Narrator
    voice_id: str
    clock: Callable[[], datetime]
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep


@dataclass(frozen=True)
class ListenAsk:
    user_id: uuid.UUID
    explainer: Explainer
    section_id: str | None
    request_id: uuid.UUID = field(default_factory=uuid.uuid4)

    @property
    def language(self) -> str:
        return self.explainer.understood.language

    def entry(self, units: int, key: str) -> LedgerEntry:
        return LedgerEntry(
            user_id=self.user_id,
            resource=VOICE_SECONDS,
            units=units,
            key=key,
            ref_type=LISTEN_LEDGER_REF,
            ref_id=str(self.explainer.answer_id),
        )


async def listen_script(ask: ListenAsk, deps: ListenDeps) -> ListenScript:
    blocks = spoken_blocks(ask.explainer, ask.section_id)
    if not blocks:
        raise ListenRefused("nothing", NOTHING_MESSAGE)
    ids = [
        narration_cache_id(block.content_hash, language=ask.language, voice_id=deps.voice_id)
        for block in blocks
    ]
    found = await asyncio.gather(
        *(stored_manifest(deps.objects, cache_id) for cache_id in dict.fromkeys(ids))
    )
    manifests = {manifest.cache_id: manifest for manifest in found if manifest is not None}
    missing = {
        cache_id: block for cache_id, block in zip(ids, blocks, strict=True) if cache_id not in manifests
    }
    if missing:
        manifests |= await _made(ask, deps, missing)
    now = deps.clock()
    tracks = [
        track
        for cache_id, block in zip(ids, blocks, strict=True)
        for track in _tracks(block, manifests[cache_id], deps.objects, now)
    ]
    return ListenScript(
        schema_version=LISTEN_SCHEMA_VERSION,
        answer_id=ask.explainer.answer_id,
        language=ask.language,
        tracks=tracks,
    )


class _Synthesis:
    def __init__(self, ask: ListenAsk, deps: ListenDeps) -> None:
        self.ask = ask
        self.deps = deps
        self.seconds = 0
        self._gate = asyncio.Semaphore(LISTEN_CONCURRENCY)

    async def manifest(self, cache_id: str, block: SpokenBlock) -> NarrationManifest:
        parts = narration_parts(block)
        made = [await self._part(cache_id, parts, index) for index in range(len(parts))]
        manifest = NarrationManifest(
            schema_version=1,
            cache_id=cache_id,
            model=NARRATION_MODEL,
            voice_id=self.deps.voice_id,
            language=self.ask.language,
            content_hash=block.content_hash,
            parts=made,
        )
        await store_manifest(self.deps.objects, manifest)
        return manifest

    async def _part(self, cache_id: str, parts: list[NarrationPart], index: int) -> NarratedPart:
        part = parts[index]
        async with self._gate:
            speech = await self.deps.narrator.narration(
                part.text,
                voice_id=self.deps.voice_id,
                language=part.language,
                previous_text=parts[index - 1].text if index else "",
                next_text=parts[index + 1].text if index + 1 < len(parts) else "",
            )
        self.seconds += speech_seconds(len(speech.audio))
        key = narration_key(cache_id, narration_file_name(self.deps.clock(), index + 1))
        await self.deps.objects.put(key, speech.audio, content_type=AUDIO_TYPE)
        return NarratedPart(
            key=key,
            language=part.language,
            duration_seconds=part_duration(speech),
            words=part_words(part, speech),
        )


async def _made(
    ask: ListenAsk, deps: ListenDeps, missing: dict[str, SpokenBlock]
) -> dict[str, NarrationManifest]:
    found = await _made_elsewhere(deps, missing)
    ours = {cache_id: block for cache_id, block in missing.items() if cache_id not in found}
    if not ours:
        return found
    try:
        return found | await _paid(ask, deps, ours)
    finally:
        await _released(deps.objects, ours)


async def _made_elsewhere(deps: ListenDeps, missing: dict[str, SpokenBlock]) -> dict[str, NarrationManifest]:
    tries = await asyncio.gather(
        *(take_lease(deps.objects, _lease_key(cid), cid, now=deps.clock()) for cid in missing)
    )
    found = await asyncio.gather(*(_waited(deps, tried) for tried in tries if not tried.ours))
    return {manifest.cache_id: manifest for manifest in found if manifest is not None}


async def _waited(deps: ListenDeps, held: LeaseTry) -> NarrationManifest | None:
    found = partial(stored_manifest, deps.objects, held.lease.cache_id)
    return await waited(found, held, clock=deps.clock, sleep=deps.sleep)


def _lease_key(cache_id: str) -> str:
    return narration_key(cache_id, LEASE_LEAF)


async def _released(objects: LeasedObjects, ours: dict[str, SpokenBlock]) -> None:
    for cache_id in ours:
        try:
            await release_lease(objects, _lease_key(cache_id))
        except AppError as error:
            logger.warning("the lease on narration %s lapses on its own: %s", cache_id, error)


async def _paid(
    ask: ListenAsk, deps: ListenDeps, missing: dict[str, SpokenBlock]
) -> dict[str, NarrationManifest]:
    characters = sum(len(part.text) for block in missing.values() for part in narration_parts(block))
    now = deps.clock()
    hold = await deps.ledger.hold(
        ask.entry(estimated_seconds(characters), listen_hold_key(ask.request_id)), now
    )
    if hold.refused:
        raise ListenRefused("quota", QUOTA_MESSAGE, retry_after=seconds_until_next_day(now))
    synthesis = _Synthesis(ask, deps)
    try:
        made = await asyncio.gather(
            *(synthesis.manifest(cache_id, block) for cache_id, block in missing.items()),
            return_exceptions=True,
        )
    finally:
        await _settled(ask, deps.ledger, hold, synthesis.seconds)
    failure = next((outcome for outcome in made if isinstance(outcome, BaseException)), None)
    if failure is not None:
        raise failure
    return {manifest.cache_id: manifest for manifest in made if isinstance(manifest, NarrationManifest)}


async def _settled(ask: ListenAsk, ledger: ListenLedger, hold: ListenHold, billed: int) -> None:
    unused = hold.held - billed
    if unused > 0:
        await ledger.record(ask.entry(-unused, listen_refund_key(ask.request_id)))
    elif unused < 0:
        extra = capped_seconds(-unused, hold.remaining_after)
        if extra:
            await ledger.record(ask.entry(extra, listen_settle_key(ask.request_id)))


def _tracks(
    block: SpokenBlock, manifest: NarrationManifest, objects: NarrationObjects, now: datetime
) -> Iterator[ListenTrack]:
    for part in manifest.parts:
        leaf = part.key.rsplit("/", 1)[-1]
        link = objects.presigned_get(
            part.key,
            disposition=content_disposition(leaf, inline=True),
            seconds=NARRATION_LINK_SECONDS,
            now=now,
        )
        yield ListenTrack(
            block_id=block.block_id,
            audio_url=link.url,
            duration_seconds=part.duration_seconds,
            words=part.words,
        )
