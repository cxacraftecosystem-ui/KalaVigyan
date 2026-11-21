from __future__ import annotations

from typing import Annotated, Any, Literal, Self

from pydantic import AfterValidator, Field, model_validator

from .component_specs_plates_parts import held_text
from .component_specs_science_parts import (
    ColourToken,
    DomId,
    EquationLine,
    FigureHead,
    FigureKey,
    Label,
    Rich,
    Species,
    SpecModel,
    StyleName,
    SvgNode,
    TextBlock,
    UnitRef,
)

__all__ = [
    "AtomKeyItem",
    "ChainEquation",
    "ChainLink",
    "ChainStep",
    "DiagramSpec",
    "EquationCardSpec",
    "HeldCite",
    "KeySwatch",
    "Molecule3dSpec",
    "MoleculeModel",
    "StructureDiagramSpec",
    "StructureMolecule",
    "checked_cite",
]

Cid = Annotated[int, Field(ge=1)]
CITE_MARK = "cite"


def checked_cite(node: dict[str, Any]) -> dict[str, Any]:
    held_text([node])
    if node.get("m") != CITE_MARK:
        raise ValueError("A record's citation is a cite mark")
    return node


HeldCite = Annotated[dict[str, Any], AfterValidator(checked_cite)]


class EquationCardSpec(SpecModel):
    kicker: UnitRef
    title: UnitRef
    mark: UnitRef
    line: EquationLine
    why: UnitRef


class ChainStep(SpecModel):
    part: Literal["step"]
    player: DomId
    step: int = Field(ge=1)
    figure: FigureKey
    figure_label: Label


class ChainEquation(SpecModel):
    part: Literal["equation"]
    style: StyleName
    label: UnitRef
    line_label: Label
    reactants: list[Species] = Field(min_length=1)
    products: list[Species] = Field(min_length=1)
    count: Label


class ChainDrawing(SpecModel):
    part: Literal["drawing"]
    drawing: SvgNode


class ChainText(SpecModel):
    part: Literal["text"]
    text: TextBlock


ChainPart = Annotated[ChainText | ChainStep | ChainDrawing | ChainEquation, Field(discriminator="part")]


class ChainLink(SpecModel):
    style: StyleName | None = None
    kicker: UnitRef
    parts: list[ChainPart] = Field(min_length=1)


class Chain(SpecModel):
    heading_id: DomId
    heading: UnitRef
    links: list[ChainLink] = Field(min_length=2)


class DiagramSpec(SpecModel):
    drawing: SvgNode | None = None
    chain: Chain | None = None

    @model_validator(mode="after")
    def _a_drawing_or_a_chain(self) -> Self:
        if (self.drawing is None) == (self.chain is None):
            raise ValueError("a diagram is one drawing or one chain of steps")
        if self.drawing is not None and self.drawing.tag != "svg":
            raise ValueError("a diagram's drawing is a whole svg")
        return self


class StructureMolecule(SpecModel):
    drawing: SvgNode
    name: Label
    formula: Rich
    note: Label
    atoms_term: UnitRef
    atoms: UnitRef
    record_term: UnitRef
    cid: Cid
    record_cite: HeldCite | None = None


class KeySwatch(SpecModel):
    colour: ColourToken
    label: Label


class StructureDiagramSpec(SpecModel):
    id: DomId
    head: FigureHead
    dek_style: StyleName | None = None
    scale: UnitRef
    molecules: list[StructureMolecule] = Field(min_length=1)
    notes: list[TextBlock] = Field(default_factory=list)
    key: Label
    swatches: list[KeySwatch] = Field(default_factory=list)
    swatch_note: TextBlock | None = None


class MoleculeModel(SpecModel):
    key: DomId
    cid: Cid
    yaw: float
    pitch: float
    name: Label
    dial_label: Label
    formula: Rich
    atoms: Label
    note: Label
    drawing: SvgNode


class AtomKeyItem(SpecModel):
    swatch: ColourToken | Literal["ring"] | None = None
    label: Label


class Molecule3dSpec(SpecModel):
    head: FigureHead
    molecules: list[MoleculeModel] = Field(min_length=1)
    side: list[TextBlock] = Field(default_factory=list)
    key: list[AtomKeyItem] = Field(min_length=1)
