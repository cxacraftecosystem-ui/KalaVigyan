from __future__ import annotations

from collections.abc import Collection, Iterator, Sequence
from typing import Annotated, Literal, Self

from pydantic import AfterValidator, Field, model_validator

from .art_kit import (
    CLOTH_FORMS,
    HEAT_SOURCES,
    KIT_MOTIONS,
    LAYERS_MAX,
    LAYERS_MIN,
    LAYOUTS,
    MOTIFS,
    PANELS_PER_LAYOUT,
    PARTS_PER_PANEL_MAX,
    PASTE_FORMS,
    PIECE_SHAPES,
    SPECIES_MARKS,
    SPECIES_PER_SCENE_MAX,
    SPECIES_ROLES,
    TOOLS,
    VESSELS,
    WATER_FORMS,
)
from .base import ContractModel, absent
from .component_specs_general import GeneralHead
from .component_specs_plates_parts import UnitRef
from .drawing_roles import MATERIAL_ROLES

__all__ = [
    "KIT_DIAGRAM",
    "UNCITED",
    "BathPart",
    "BlockPart",
    "ClothPart",
    "DeclaredDiagramSpec",
    "HeatPart",
    "KitPanel",
    "KitPartSpec",
    "KitPrint",
    "PastePart",
    "PiecePart",
    "SectionLayer",
    "SectionPart",
    "SpeciesPart",
    "ToolPart",
    "WaterPart",
    "kit_label_problems",
    "kit_labels",
    "motion_problem",
    "part_labels",
    "parts_problem",
]

KIT_DIAGRAM = "diagram"
TOKEN_PREFIX = "--"
NOT_RECORDED = (
    "{token} is not a depicted material the design system records: a kit part takes a --dye-* or --dip-* "
    "material by its token, and a material no record holds is asked for first"
)
UNCITED = (
    "the unit {ref}, the label of {where}, cites no fact: a kit part's label rests on the facts that state it"
)
SPECIES = "species"
PRODUCT = "product"
REACTANT = "reactant"
MOTION_NEEDS = {
    "dip": ("bath", "a bath part with a piece in it"),
    "take": ("cloth", "a cloth part"),
    "dry": ("paste", "a paste part that names what it dries to"),
    "react": (SPECIES, "a product species part and a species it is made from"),
}
TOO_MANY_PARTS = (
    "a {holder} holds at most {most} parts, or at most {species} when every part is a species of one reaction, "
    "not {count}"
)
ONLY_A_REACTANT_BREAKS = (
    "only a reactant breaks: the bond-break mark is drawn on the species a bond breaks in"
)
COLOUR_OR_MARK = "a species is drawn in its material's colour or by its mark (clear, gas or ion), not both"


def _material(token: str) -> str:
    if not token.startswith(TOKEN_PREFIX) or token.removeprefix(TOKEN_PREFIX) not in MATERIAL_ROLES:
        raise ValueError(NOT_RECORDED.format(token=token))
    return token


Material = Annotated[str, AfterValidator(_material)]
Motif = Literal[*MOTIFS]


class KitPrint(ContractModel):
    motif: Motif
    material: Material


class ClothPart(ContractModel):
    part: Literal["cloth"]
    form: Literal[*CLOTH_FORMS]
    material: Material
    printed: KitPrint | None = Field(default=None, exclude_if=absent)
    label: UnitRef


class BlockPart(ContractModel):
    part: Literal["block"]
    motif: Motif
    paste: Material | None = Field(default=None, exclude_if=absent)
    label: UnitRef


class BathPart(ContractModel):
    part: Literal["bath"]
    vessel: Literal[*VESSELS]
    liquor: Material | None = Field(default=None, exclude_if=absent)
    piece: Material | None = Field(default=None, exclude_if=absent)
    label: UnitRef


class PastePart(ContractModel):
    part: Literal["paste"]
    form: Literal[*PASTE_FORMS]
    material: Material
    on: Material | None = Field(default=None, exclude_if=absent)
    dried: Material | None = Field(default=None, exclude_if=absent)
    label: UnitRef


class HeatPart(ContractModel):
    part: Literal["heat"]
    source: Literal[*HEAT_SOURCES]
    label: UnitRef


class WaterPart(ContractModel):
    part: Literal["water"]
    form: Literal[*WATER_FORMS]
    label: UnitRef


class ToolPart(ContractModel):
    part: Literal["tool"]
    tool: Literal[*TOOLS]
    held: bool = True
    load: Material | None = Field(default=None, exclude_if=absent)
    label: UnitRef


class SectionLayer(ContractModel):
    material: Material | Literal["earth"]
    label: UnitRef


class SectionPart(ContractModel):
    part: Literal["section"]
    layers: list[SectionLayer] = Field(min_length=LAYERS_MIN, max_length=LAYERS_MAX)
    label: UnitRef


class PiecePart(ContractModel):
    part: Literal["piece"]
    shape: Literal[*PIECE_SHAPES]
    material: Material | None = Field(default=None, exclude_if=absent)
    inlay: KitPrint | None = Field(default=None, exclude_if=absent)
    label: UnitRef


class SpeciesPart(ContractModel):
    part: Literal["species"]
    role: Literal[*SPECIES_ROLES]
    material: Material | None = Field(default=None, exclude_if=absent)
    mark: Literal[*SPECIES_MARKS] | None = Field(default=None, exclude_if=absent)
    breaks: bool = False
    label: UnitRef

    @model_validator(mode="after")
    def _a_reactant_breaks_and_one_way_to_draw(self) -> Self:
        if self.breaks and self.role != REACTANT:
            raise ValueError(ONLY_A_REACTANT_BREAKS)
        if self.material is not None and self.mark is not None:
            raise ValueError(COLOUR_OR_MARK)
        return self

    @property
    def uncoloured(self) -> bool:
        return self.material is None and self.mark is None


KitPartSpec = Annotated[
    ClothPart
    | BlockPart
    | BathPart
    | PastePart
    | HeatPart
    | WaterPart
    | ToolPart
    | SectionPart
    | PiecePart
    | SpeciesPart,
    Field(discriminator="part"),
]


class KitPanel(ContractModel):
    label: UnitRef
    text: UnitRef | None = Field(default=None, exclude_if=absent)
    via: UnitRef | None = Field(default=None, exclude_if=absent)
    motion: Literal[*KIT_MOTIONS] | None = Field(default=None, exclude_if=absent)
    parts: list[KitPartSpec] = Field(min_length=1, max_length=SPECIES_PER_SCENE_MAX)

    @model_validator(mode="after")
    def _motion_explains_a_part(self) -> Self:
        problem = parts_problem(self.parts, "panel") or motion_problem(self.motion, self.parts, "panel")
        if problem is not None:
            raise ValueError(problem)
        return self


class DeclaredDiagramSpec(ContractModel):
    head: GeneralHead
    layout: Literal[*LAYOUTS]
    alt: UnitRef
    panels: list[KitPanel] = Field(min_length=1, max_length=PANELS_PER_LAYOUT["steps"][1])

    @model_validator(mode="after")
    def _laid_out(self) -> Self:
        low, high = PANELS_PER_LAYOUT[self.layout]
        if not low <= len(self.panels) <= high:
            raise ValueError(
                f"a {self.layout} diagram has {_count(low, high)} panels, not {len(self.panels)}"
            )
        if self.layout == "section" and [part.part for part in self.panels[0].parts] != ["section"]:
            raise ValueError("a section diagram's one panel holds one section part and nothing else")
        arrows = self.layout in ("sequence", "before_after")
        if any(panel.via is not None for panel in self.panels[: 1 if arrows else None]):
            raise ValueError(
                "only a sequence or a before and after names a change, on the arrow into a later panel"
            )
        return self


def motion_problem(motion: str | None, parts: Sequence[object], holder: str) -> str | None:
    if motion is None:
        return None
    name, needs = MOTION_NEEDS[motion]
    if any(_moves(part, name) for part in parts) and (name != SPECIES or _made_from(parts)):
        return None
    return f"the {motion} motion explains {needs}, which this {holder} does not hold"


def parts_problem(parts: Sequence[object], holder: str) -> str | None:
    if len(parts) <= PARTS_PER_PANEL_MAX or all(isinstance(part, SpeciesPart) for part in parts):
        return None
    return TOO_MANY_PARTS.format(
        holder=holder, most=PARTS_PER_PANEL_MAX, species=SPECIES_PER_SCENE_MAX, count=len(parts)
    )


def part_labels(parts: Sequence[KitPartSpec], where: str) -> Iterator[tuple[str, str]]:
    for part in parts:
        yield part.label, f"{where}'s {part.part} part"
        if isinstance(part, SectionPart):
            for depth, layer in enumerate(part.layers, start=1):
                yield layer.label, f"layer {depth} of {where}'s section"


def kit_labels(spec: DeclaredDiagramSpec) -> Iterator[tuple[str, str]]:
    for at, panel in enumerate(spec.panels, start=1):
        yield from part_labels(panel.parts, f"panel {at}")


def kit_label_problems(spec: DeclaredDiagramSpec, cited: Collection[str]) -> list[str]:
    return [UNCITED.format(ref=ref, where=where) for ref, where in kit_labels(spec) if ref not in cited]


def _moves(part: object, name: str) -> bool:
    if name == "bath":
        return isinstance(part, BathPart) and part.piece is not None
    if name == "paste":
        return isinstance(part, PastePart) and part.dried is not None
    if name == SPECIES:
        return isinstance(part, SpeciesPart) and part.role == PRODUCT
    return isinstance(part, ClothPart)


def _made_from(parts: Sequence[object]) -> bool:
    return any(isinstance(part, SpeciesPart) and part.role != PRODUCT for part in parts)


def _count(low: int, high: int) -> str:
    return str(low) if low == high else f"{low} to {high}"
