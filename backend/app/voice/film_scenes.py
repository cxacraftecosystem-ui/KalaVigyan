from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass

from app.research.blocks import BlockBase, ImagesBlock, ProcessLadderBlock
from app.research.blocks_matter import ReactionPlayerBlock
from app.research.blocks_place import RegionStoryBlock
from app.research.blocks_play import SimulationBlock
from app.research.explainer import Explainer
from app.schemas.film import FILM_SCENE_SECONDS, SCORE_CUES_MAX

from .narration import SpokenBlock, estimated_seconds, narration_parts, spoken_blocks
from .score_prompts import RIVER_FACET, SCORE_PROMPT_VERSION, STAGE_FACETS, CuePrompt, cue_prompt

__all__ = [
    "BED_SECONDS_MAX",
    "BED_SECONDS_MIN",
    "BED_STEP_SECONDS",
    "FilmScene",
    "SceneCue",
    "bed_seconds",
    "cue_facet",
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
    facet: str | None
    seconds: float


@dataclass(frozen=True)
class SceneCue:
    scene: FilmScene
    cue: CuePrompt


def film_scenes(explainer: Explainer, *, heard: Mapping[str, float] | None = None) -> list[FilmScene]:
    narrated = {block.block_id: _narrated_seconds(block) for block in spoken_blocks(explainer, None)}
    if heard and set(narrated) <= set(heard):
        narrated = {block_id: heard[block_id] for block_id in narrated}
    opening: list[BlockBase] = [] if explainer.lede is None else [explainer.lede]
    drawn = opening + [
        block
        for section in sorted(explainer.sections, key=lambda section: section.order)
        for block in section.blocks
        if not (isinstance(block, SimulationBlock) and block.hidden)
    ]
    return [
        FilmScene(
            number=number,
            block_id=block.id,
            kind=block.kind,
            facet=cue_facet(block),
            seconds=narrated.get(block.id) or held_seconds(block),
        )
        for number, block in enumerate(drawn, start=1)
    ]


def cue_facet(block: BlockBase) -> str | None:
    if isinstance(block, ProcessLadderBlock):
        facets = [
            STAGE_FACETS[stage.stage_type] for stage in block.stages if stage.stage_type in STAGE_FACETS
        ]
        return max(Counter(facets).items(), key=lambda pair: pair[1])[0] if facets else None
    if isinstance(block, RegionStoryBlock) and block.river is not None:
        return RIVER_FACET
    return None


def held_seconds(block: BlockBase) -> float:
    if isinstance(block, ReactionPlayerBlock | RegionStoryBlock):
        return FILM_SCENE_SECONDS["step"] * len(block.steps)
    if isinstance(block, ImagesBlock):
        return FILM_SCENE_SECONDS["picture"] * len(block.items)
    return FILM_SCENE_SECONDS["block"]


def scenes_hash(scenes: list[FilmScene]) -> str:
    scenes_seen = [[scene.block_id, scene.kind, scene.facet] for scene in scenes]
    text = json.dumps([SCORE_PROMPT_VERSION, scenes_seen], separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def bed_seconds(scenes: list[FilmScene]) -> float:
    total = sum(scene.seconds for scene in scenes)
    rounded = math.ceil(total / BED_STEP_SECONDS) * BED_STEP_SECONDS
    return float(min(BED_SECONDS_MAX, max(BED_SECONDS_MIN, rounded)))


def scene_cues(scenes: list[FilmScene]) -> list[SceneCue]:
    cued = [SceneCue(scene, cue) for scene in scenes if (cue := cue_prompt(scene.kind, scene.facet))]
    return cued[:SCORE_CUES_MAX]


def _narrated_seconds(block: SpokenBlock) -> float:
    return float(estimated_seconds(sum(len(part.text) for part in narration_parts(block))))
