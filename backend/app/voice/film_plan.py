from __future__ import annotations

import asyncio
from dataclasses import dataclass

from app.providers.elevenlabs import NARRATION_MODEL
from app.research.explainer import Explainer

from .film_scenes import FilmScene, bed_seconds, film_scenes, scenes_hash
from .narration import narration_cache_id, spoken_blocks
from .narration_cache import NarrationObjects, stored_manifest
from .score_cache import ScoreManifest

__all__ = ["ScorePlan", "heard_seconds", "score_plan"]


@dataclass(frozen=True)
class ScorePlan:
    scenes: list[FilmScene]
    digest: str
    bed: float

    def matches(self, manifest: ScoreManifest) -> bool:
        music = manifest.music
        return (
            manifest.scenes_hash == self.digest and music is not None and music.duration_seconds == self.bed
        )


async def score_plan(explainer: Explainer, objects: NarrationObjects, voice_id: str | None) -> ScorePlan:
    heard = await heard_seconds(explainer, objects, voice_id) if voice_id else {}
    scenes = film_scenes(explainer, heard=heard)
    return ScorePlan(scenes=scenes, digest=scenes_hash(scenes), bed=bed_seconds(scenes) if scenes else 0.0)


async def heard_seconds(explainer: Explainer, objects: NarrationObjects, voice_id: str) -> dict[str, float]:
    language = explainer.understood.language
    blocks = spoken_blocks(explainer, None)
    ids = [
        narration_cache_id(block.content_hash, language=language, voice_id=voice_id, model=NARRATION_MODEL)
        for block in blocks
    ]
    found = await asyncio.gather(*(stored_manifest(objects, cache_id) for cache_id in ids))
    heard: dict[str, float] = {}
    for block, manifest in zip(blocks, found, strict=True):
        if manifest is None:
            return {}
        heard[block.block_id] = round(sum(part.duration_seconds for part in manifest.parts), 3)
    return heard
