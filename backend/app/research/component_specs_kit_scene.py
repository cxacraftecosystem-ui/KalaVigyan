from __future__ import annotations

from collections.abc import Collection, Iterator, Mapping
from typing import Annotated, Any, Literal, Self

from pydantic import AfterValidator, BaseModel, Discriminator, Field, Tag, model_validator
from pydantic.alias_generators import to_camel

from .art_kit import KIT_MOTIONS, SPECIES_PER_SCENE_MAX
from .base import ContractModel, absent
from .component_specs_kit import UNCITED, KitPartSpec, motion_problem, part_labels, parts_problem
from .component_specs_plates_parts import DrawingElement
from .component_specs_science_parts import SvgNode

__all__ = [
    "DRAWN",
    "KIT",
    "KIT_SCENE_KINDS",
    "KIT_SCENE_MARK",
    "KitScene",
    "SceneDrawing",
    "SealDrawing",
    "StepArt",
    "StillDrawing",
    "kit_scene_label_problems",
    "kit_scenes",
    "scene_form",
]

KIT_SCENE_KINDS = frozenset({"reaction_player", "dip_player", "stage_player", "choice_toggle", "label_card"})
KIT_SCENE_MARK = "parts"
DRAWN = "drawn"
KIT = "kit"
STILL = (
    "a kit scene here names no motion: this scene rests as the reader sees it, and only a reaction step, a dip "
    "phase, a dip player's scene or a stage's own scene is shown again when the reader presses"
)


class KitScene(ContractModel):
    parts: list[KitPartSpec] = Field(min_length=1, max_length=SPECIES_PER_SCENE_MAX)
    motion: Literal[*KIT_MOTIONS] | None = Field(default=None, exclude_if=absent)

    @model_validator(mode="after")
    def _motion_explains_a_part(self) -> Self:
        problem = parts_problem(self.parts, "scene") or motion_problem(self.motion, self.parts, "scene")
        if problem is not None:
            raise ValueError(problem)
        return self


def _still(scene: KitScene) -> KitScene:
    if scene.motion is not None:
        raise ValueError(STILL)
    return scene


def scene_form(value: Any) -> str:
    if isinstance(value, KitScene) or (isinstance(value, Mapping) and KIT_SCENE_MARK in value):
        return KIT
    return DRAWN


KitStill = Annotated[KitScene, AfterValidator(_still)]
SceneDrawing = Annotated[
    Annotated[SvgNode, Tag(DRAWN)] | Annotated[KitScene, Tag(KIT)],
    Discriminator(scene_form),
]
StillDrawing = Annotated[
    Annotated[SvgNode, Tag(DRAWN)] | Annotated[KitStill, Tag(KIT)],
    Discriminator(scene_form),
]
StepArt = Annotated[
    Annotated[list[SvgNode], Field(min_length=1), Tag(DRAWN)] | Annotated[KitScene, Tag(KIT)],
    Discriminator(scene_form),
]
SealDrawing = Annotated[
    Annotated[DrawingElement, Tag(DRAWN)] | Annotated[KitStill, Tag(KIT)],
    Discriminator(scene_form),
]


def kit_scenes(value: object, path: str = "") -> Iterator[tuple[str, KitScene]]:
    if isinstance(value, KitScene):
        yield path, value
    elif isinstance(value, BaseModel):
        for name in type(value).model_fields:
            field = to_camel(name)
            yield from kit_scenes(getattr(value, name), f"{path}.{field}" if path else field)
    elif isinstance(value, list | tuple):
        for at, item in enumerate(value):
            yield from kit_scenes(item, f"{path}[{at}]")


def kit_scene_label_problems(spec: object, cited: Collection[str]) -> list[str]:
    return [
        UNCITED.format(ref=ref, where=where)
        for path, scene in kit_scenes(spec)
        for ref, where in part_labels(scene.parts, f"the kit scene at {path}")
        if ref not in cited
    ]
