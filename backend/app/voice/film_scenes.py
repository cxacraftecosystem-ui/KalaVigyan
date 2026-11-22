from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass

from app.research.blocks import BlockBase, ImagesBlock
from app.research.blocks_matter import ReactionPlayerBlock
from app.research.blocks_place import RegionStoryBlock
from app.research.blocks_play import SimulationBlock
from app.research.explainer import Explainer
from app.schemas.film import FILM_SCENE_SECONDS, SCORE_CUES_MAX

from .narration import SpokenBlock, estimated_seconds, narration_parts, spoken_blocks
from .score_prompts import CuePrompt, cue_prompt

__all__ = [
    "BED_SECONDS_MAX",
    "BED_SECONDS_MIN",
    "BED_STEP_SECONDS",
    "FilmScene",
    "SceneCue",
    "bed_seconds",
    "film_scenes",
    "held_seconds",
    "scene_cues",
    "scenes_hash",
]

BED_SECONDS_MIN = 30
BED_SECONDS_MAX = 180
BED_STEP_SECONDS = 10


@dataclass(frozen=True)
class FilmScene:
    number: int
    block_id: str
    kind: str
    discipline: str | None
    seconds: float


@dataclass(frozen=True)
class SceneCue:
    scene: FilmScene
    cue: CuePrompt


def film_scenes(explainer: Explainer) -> list[FilmScene]:
    narrated = {block.block_id: _narrated_seconds(block) for block in spoken_blocks(explainer, None)}
    opening: list[tuple[str | None, BlockBase]] = [] if explainer.lede is None else [(None, explainer.lede)]
    drawn = opening + [
        (section.discipline, block)
        for section in sorted(explainer.sections, key=lambda section: section.order)
        for block in section.blocks
        if not (isinstance(block, SimulationBlock) and block.hidden)
    ]
    return [
        FilmScene(
            number=number,
            block_id=block.id,
            kind=block.kind,
            discipline=discipline,
            seconds=narrated.get(block.id) or held_seconds(block),
        )
        for number, (discipline, block) in enumerate(drawn, start=1)
    ]


def held_seconds(block: BlockBase) -> float:
    if isinstance(block, ReactionPlayerBlock | RegionStoryBlock):
        return FILM_SCENE_SECONDS["step"] * len(block.steps)
    if isinstance(block, ImagesBlock):
        return FILM_SCENE_SECONDS["picture"] * len(block.items)
    return FILM_SCENE_SECONDS["block"]


def scenes_hash(scenes: list[FilmScene]) -> str:
    pairs = [[scene.block_id, scene.kind] for scene in scenes]
    return hashlib.sha256(json.dumps(pairs, separators=(",", ":")).encode("utf-8")).hexdigest()


def bed_seconds(scenes: list[FilmScene]) -> float:
    total = sum(scene.seconds for scene in scenes)
    rounded = math.ceil(total / BED_STEP_SECONDS) * BED_STEP_SECONDS
    return float(min(BED_SECONDS_MAX, max(BED_SECONDS_MIN, rounded)))


def scene_cues(scenes: list[FilmScene]) -> list[SceneCue]:
    cued = [SceneCue(scene, cue) for scene in scenes if (cue := cue_prompt(scene.kind, scene.discipline))]
    return cued[:SCORE_CUES_MAX]


def _narrated_seconds(block: SpokenBlock) -> float:
    return float(estimated_seconds(sum(len(part.text) for part in narration_parts(block))))
