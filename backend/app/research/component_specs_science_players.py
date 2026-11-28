from __future__ import annotations

from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from .base import absent
from .component_specs_kit_scene import SceneDrawing, StepArt, StillDrawing
from .component_specs_science_parts import (
    Colour,
    ColourToken,
    Differs,
    DomId,
    Equation,
    FigureHead,
    HookLabel,
    Label,
    Rich,
    ShownRich,
    SpecModel,
    Styled,
    SvgNode,
    UnitRef,
)

__all__ = [
    "DRAWN_STAGE",
    "PHASE_KEY_PATTERN",
    "REST_SCENE",
    "Condition",
    "DipPhase",
    "DipPlayerSpec",
    "LaneArrow",
    "LanePlus",
    "LaneSpecies",
    "ReactionPlayerSpec",
    "ReactionStep",
    "StageEntry",
    "StagePlayerSpec",
    "StepChemistry",
    "StepEquation",
    "StepLane",
    "StepNoEquation",
    "StepScene",
    "StepText",
]

PHASE_KEY_PATTERN = r"^[a-z][a-z0-9]*(-[a-z0-9]+)*$"
PHASE_KEY_MAX = 40
DRAWN_STAGE = "stage {name}'s scene drawn by hand is one whole svg drawing, as the player's drawing is"
REST_SCENE = (
    "the last stage, where the player rests, is drawn by the player's drawing: give that picture as drawing "
    "and leave the last stage without a scene of its own"
)
SWATCH_MARKS = ("clear", "gas", "ion")
Cid = Annotated[int, Field(ge=1)]
PhaseKey = Annotated[str, Field(pattern=PHASE_KEY_PATTERN, max_length=PHASE_KEY_MAX)]


class Condition(SpecModel):
    term: UnitRef
    value: UnitRef


class StepText(SpecModel):
    kicker: UnitRef
    heading: UnitRef
    paragraphs: list[UnitRef] = Field(min_length=1)
    bond: Label | None = None
    link: UnitRef | None = None
    conditions: list[Condition] = Field(default_factory=list)
    differs: Differs | None = None


class LaneSpecies(SpecModel):
    item: Literal["species"]
    swatch: Colour | Literal[*SWATCH_MARKS]
    name: ShownRich
    formula: Rich | None = None
    state: list[str | Styled] = Field(default_factory=list)
    cid: Cid | None = None


class LanePlus(SpecModel):
    item: Literal["plus"]


class LaneArrow(SpecModel):
    item: Literal["arrow"]
    label: Label


LaneItem = Annotated[LaneSpecies | LanePlus | LaneArrow, Field(discriminator="item")]


class StepLane(SpecModel):
    part: Literal["lane"]
    label: Label
    items: list[LaneItem] = Field(min_length=1)


class StepEquation(SpecModel):
    part: Literal["equation"]
    equation: Equation


class StepNoEquation(SpecModel):
    part: Literal["none"]
    unit: UnitRef


ChemistryPart = Annotated[StepLane | StepEquation | StepNoEquation, Field(discriminator="part")]


class StepChemistry(SpecModel):
    parts: list[ChemistryPart] = Field(min_length=2)

    @model_validator(mode="after")
    def _species_then_an_equation_or_why_not(self) -> Self:
        kinds = [part.part for part in self.parts]
        if kinds[0] != "lane" or not {"equation", "none"} & set(kinds):
            raise ValueError("a step names its species, then shows its equation or says why it has none")
        return self


class StepScene(SpecModel):
    where_icon: SvgNode | None = Field(default=None, exclude_if=absent)
    where: UnitRef
    art: StepArt

    @model_validator(mode="after")
    def _drawn_art_shows_where(self) -> Self:
        if isinstance(self.art, list) and self.where_icon is None:
            raise ValueError(
                "a step drawn by hand shows its where icon; a kit scene draws where it happens itself"
            )
        return self


class ReactionStep(SpecModel):
    name: Label
    text: StepText
    chemistry: StepChemistry
    scene: StepScene | None = None


class ReactionPlayerSpec(SpecModel):
    id: DomId
    track: HookLabel
    head: FigureHead
    current: int = Field(ge=1)
    steps: list[ReactionStep] = Field(min_length=2)
    scenes: list[SvgNode] = Field(default_factory=list)
    key: Label | None = None
    status: UnitRef

    @model_validator(mode="after")
    def _one_way_of_drawing_and_a_step_at_rest(self) -> Self:
        if self.current > len(self.steps):
            raise ValueError(f"player {self.id} rests on step {self.current} of {len(self.steps)}")
        drawn = [step.scene is not None for step in self.steps]
        if any(drawn) and (not all(drawn) or self.scenes):
            raise ValueError(f"player {self.id} draws every step's reaction or one scene, not both")
        if not any(drawn) and (not self.scenes or self.key is not None):
            raise ValueError(f"player {self.id} without step reactions draws its scene")
        return self


class DipPhase(SpecModel):
    pose: PhaseKey
    drawing: SceneDrawing
    kicker: UnitRef
    text: UnitRef


class DipPlayerSpec(SpecModel):
    id: DomId
    head: FigureHead
    phase: UnitRef
    scene: SceneDrawing
    strip_label: Label
    phases: list[DipPhase] = Field(min_length=2)
    dip_again: Label
    status: UnitRef
    dips_label: UnitRef
    dips: list[ColourToken] = Field(min_length=1)
    equation: Equation | None = Field(default=None, exclude_if=absent)

    @model_validator(mode="after")
    def _each_phase_once(self) -> Self:
        poses = [phase.pose for phase in self.phases]
        if len(set(poses)) != len(poses):
            raise ValueError(f"player {self.id} names each of its phases once")
        return self


class StageEntry(SpecModel):
    name: Label
    english: Label
    local: bool
    after: Label
    number: UnitRef
    heading: UnitRef
    texts: list[UnitRef] = Field(min_length=1)
    why: UnitRef | None = None
    differs: Differs | None = None
    after_sentence: UnitRef | None = None
    materials: UnitRef | None = None
    swatch: ColourToken | None = Field(default=None, exclude_if=absent)
    scene: SceneDrawing | None = Field(default=None, exclude_if=absent)

    @model_validator(mode="after")
    def _a_drawn_scene_is_one_drawing(self) -> Self:
        if isinstance(self.scene, SvgNode) and self.scene.tag != "svg":
            raise ValueError(DRAWN_STAGE.format(name=self.name))
        return self


class StageFinish(SpecModel):
    heading: UnitRef
    paragraphs: list[UnitRef] = Field(min_length=1)


class StagePlayerSpec(SpecModel):
    key: DomId
    head: FigureHead
    drawing: StillDrawing
    rest_name: UnitRef
    play: Label
    source: UnitRef
    stages: list[StageEntry] = Field(min_length=2)
    finish: StageFinish
    after_label: Label

    @model_validator(mode="after")
    def _rests_on_its_drawing(self) -> Self:
        if self.stages[-1].scene is not None:
            raise ValueError(REST_SCENE)
        return self
