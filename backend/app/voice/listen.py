from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterator
from datetime import datetime

from app.core.errors import ExternalFailure, NotConfigured
from app.schemas.listen import LISTEN_POLL_SECONDS, LISTEN_SCHEMA_VERSION, ListenScript, ListenTrack
from app.services.naming import content_disposition

from .listen_ask import ListenAsk, ListenDeps, ListenRefused
from .listen_making import first_block_made
from .listen_voices import ListenVoice
from .narration import SpokenBlock, narration_cache_id, spoken_blocks
from .narration_cache import NarrationManifest, NarrationObjects, stored_manifest

__all__ = [
    "NARRATION_LINK_SECONDS",
    "NOTHING_MESSAGE",
    "listen_script",
]

logger = logging.getLogger(__name__)

NARRATION_LINK_SECONDS = 3600
NOTHING_MESSAGE = "There is nothing to read aloud here."
VOICE_NAME = "LISTEN_VOICE"

Reading = list[tuple[str, SpokenBlock]]


async def listen_script(ask: ListenAsk, deps: ListenDeps) -> ListenScript:
    blocks = spoken_blocks(ask.explainer, ask.section_id)
    if not blocks:
        raise ListenRefused("nothing", NOTHING_MESSAGE)
    voices = [
        voice for voice in deps.voices if voice.speaks(ask.language) and ask.voice in (None, voice.name)
    ]
    if not voices:
        raise NotConfigured(VOICE_NAME, f"no voice reads {ask.language} aloud as {ask.voice or 'any voice'}")
    for voice in voices[:-1]:
        try:
            return await _voiced(ask, deps, voice, blocks)
        except ExternalFailure as failure:
            if failure.service != voice.service:
                raise
            logger.warning("Listen reads with the next voice, since %s failed: %s", voice.name, failure)
    return await _voiced(ask, deps, voices[-1], blocks)


async def _voiced(
    ask: ListenAsk, deps: ListenDeps, voice: ListenVoice, blocks: list[SpokenBlock]
) -> ListenScript:
    reading = [
        (
            narration_cache_id(
                block.content_hash, language=ask.language, voice_id=voice.voice_id, model=voice.model
            ),
            block,
        )
        for block in blocks
    ]
    found = await asyncio.gather(
        *(stored_manifest(deps.objects, cache_id) for cache_id in dict.fromkeys(cid for cid, _ in reading))
    )
    manifests = {manifest.cache_id: manifest for manifest in found if manifest is not None}
    missing = {cache_id: block for cache_id, block in reading if cache_id not in manifests}
    if missing:
        manifests |= await first_block_made(ask, deps, voice, missing, reading[0][0])
    return _script(ask, deps, voice, reading, manifests)


def _script(
    ask: ListenAsk,
    deps: ListenDeps,
    voice: ListenVoice,
    reading: Reading,
    manifests: dict[str, NarrationManifest],
) -> ListenScript:
    ready = next((at for at, (cache_id, _) in enumerate(reading) if cache_id not in manifests), len(reading))
    now = deps.clock()
    pending = [block.block_id for _, block in reading[ready:]]
    return ListenScript(
        schema_version=LISTEN_SCHEMA_VERSION,
        answer_id=ask.explainer.answer_id,
        language=ask.language,
        voice=voice.name,
        tracks=[
            track
            for cache_id, block in reading[:ready]
            for track in _tracks(block, manifests[cache_id], deps.objects, now)
        ],
        pending=pending,
        poll_after_seconds=LISTEN_POLL_SECONDS if pending else None,
    )


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
            sentences=part.sentences,
        )
