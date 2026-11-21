from __future__ import annotations

import re
from typing import Annotated, Literal

from pydantic import AfterValidator, ConfigDict, Field, field_validator

from .base import ContractModel
from .depicted_materials import DEPICTED_MATERIALS

__all__ = [
    "COLOUR_TOKEN_PATTERN",
    "SVG_TAGS",
    "UNIT_REF_PATTERN",
    "AtomRow",
    "AtomTable",
    "Colour",
    "ColourMix",
    "ColourToken",
    "ComponentSlot",
    "Differs",
    "DomId",
    "Equation",
    "EquationLine",
    "FigureHead",
    "FigureKey",
    "Label",
    "Rich",
    "SpecModel",
    "Species",
    "StyleName",
    "Styled",
    "SvgNode",
    "TextBlock",
    "UnitRef",
    "known_colour_token",
]

UNIT_REF_PATTERN = r"^u\d{4,}$"
DOM_ID_PATTERN = r"^[A-Za-z][\w-]*$"
STYLE_PATTERN = r"^[a-z][a-z0-9-]*( [a-z][a-z0-9-]*)*$"
FIGURE_KEY_PATTERN = r"^[a-z]+:[A-Za-z0-9.]+$"
COMPONENT_LABEL_PATTERN = r"^[a-z0-9]+(-[a-z0-9]+)*(/[a-z0-9]+(-[a-z0-9]+)*){2,}$"
COLOUR_TOKEN_PATTERN = (
    r"^--(ground|raised|sunk|rule|rule-strong|ink-[1-3]|madder|indigo|dye-[a-z]+(-[a-z]+)*|dip-[1-9]"
    r"|mol-[a-z]+|atom-[a-z]+|map-[a-z]+(-[a-z]+)*|chart-[a-z]+(-[a-z]+)*)$"
)
SVG_TAGS = (
    "svg",
    "g",
    "defs",
    "title",
    "desc",
    "clipPath",
    "mask",
    "marker",
    "pattern",
    "linearGradient",
    "stop",
    "filter",
    "feColorMatrix",
    "feComponentTransfer",
    "feFuncR",
    "feFuncG",
    "feFuncB",
    "rect",
    "path",
    "circle",
    "ellipse",
    "line",
    "polygon",
    "text",
    "tspan",
)
SVG_ATTRIBUTE_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9-]*$")
PAINT_ATTRIBUTES = frozenset({"fill", "stroke", "stop-color"})
PAINT_VALUE = re.compile(
    r"^(none|currentColor|#fff|#000|url\(#[\w-]+\)|rgba\((255,255,255|0,0,0),(0|1|0?\.\d+)\))$"
)
PAINT_TOKEN = re.compile(r"^var\((--[a-z0-9-]+)\)$")
PAINT_MIX = re.compile(r"^color-mix\(in srgb, var\((--[a-z0-9-]+)\) \d{1,3}%, var\((--[a-z0-9-]+)\)\)$")
LOCAL_URL = re.compile(r"url\((?!#[\w-]+\))")
DEPICTED_PREFIX = "--dye-"
DEPICTED = frozenset(DEPICTED_MATERIALS)

UnitRef = Annotated[str, Field(pattern=UNIT_REF_PATTERN)]
DomId = Annotated[str, Field(pattern=DOM_ID_PATTERN)]
StyleName = Annotated[str, Field(pattern=STYLE_PATTERN)]
FigureKey = Annotated[str, Field(pattern=FIGURE_KEY_PATTERN)]


def known_colour_token(token: str) -> bool:
    if not re.fullmatch(COLOUR_TOKEN_PATTERN, token):
        return False
    return not token.startswith(DEPICTED_PREFIX) or token.removeprefix(DEPICTED_PREFIX) in DEPICTED


def _depicted(token: str) -> str:
    if not known_colour_token(token):
        raise ValueError(f"{token} is not a depicted material the design system records")
    return token


ColourToken = Annotated[str, Field(pattern=COLOUR_TOKEN_PATTERN), AfterValidator(_depicted)]
Label = Annotated[str, Field(min_length=1, max_length=2000)]


class SpecModel(ContractModel):
    model_config = ConfigDict(**{**ContractModel.model_config, "str_strip_whitespace": False})


class Styled(SpecModel):
    text: str = Field(min_length=1)
    style: Literal["i", "b", "sub", "sup"]


Rich = Annotated[list[str | Styled], Field(min_length=1)]


class SvgNode(SpecModel):
    tag: Literal[*SVG_TAGS]
    attrs: dict[str, str] = Field(default_factory=dict, exclude_if=lambda value: not value)
    children: list[SvgNode | str] = Field(default_factory=list, exclude_if=lambda value: not value)

    @field_validator("attrs")
    @classmethod
    def _drawing_attributes_only(cls, attrs: dict[str, str]) -> dict[str, str]:
        for name, value in attrs.items():
            refused = _refused_attribute(name, value)
            if refused:
                raise ValueError(f"drawing attribute {name}={value!r}: {refused}")
        return attrs


class ColourMix(SpecModel):
    first: ColourToken
    share: int = Field(ge=1, le=99)
    second: ColourToken


Colour = ColourToken | ColourMix


class TextBlock(SpecModel):
    tag: Literal["p", "h2", "h3", "h4"]
    style: StyleName | None = None
    unit: UnitRef


class ComponentSlot(SpecModel):
    component: str = Field(pattern=COMPONENT_LABEL_PATTERN)


class FigureHead(SpecModel):
    figure: FigureKey | None
    number: UnitRef
    title: UnitRef
    title_id: DomId | None = None
    dek: UnitRef | None = None


class Species(SpecModel):
    formula: Rich
    name: Label | None = None


class EquationLine(SpecModel):
    reactants: list[Species] = Field(min_length=1)
    products: list[Species] = Field(min_length=1)


class AtomRow(SpecModel):
    element: UnitRef
    left: UnitRef
    right: UnitRef


class AtomTable(SpecModel):
    caption: Label
    head: list[UnitRef] = Field(min_length=4, max_length=4)
    rows: list[AtomRow] = Field(min_length=1)


class Equation(SpecModel):
    label: Label
    style: StyleName | None = None
    line: EquationLine
    atoms: AtomTable | None = None
    notes: list[UnitRef] = Field(default_factory=list)


class Differs(SpecModel):
    summary: Label
    body: list[UnitRef] = Field(min_length=1)


def _refused_attribute(name: str, value: str) -> str | None:
    if not SVG_ATTRIBUTE_NAME.fullmatch(name) or name.lower().startswith("on"):
        return "not a drawing attribute"
    if "javascript:" in value.lower() or LOCAL_URL.search(value):
        return "only in-drawing references are allowed"
    if name in PAINT_ATTRIBUTES and not _paint(value):
        return "paint is a token, a local reference, none or a mask's white or black"
    return None


def _paint(value: str) -> bool:
    tokens = PAINT_TOKEN.fullmatch(value) or PAINT_MIX.fullmatch(value)
    if tokens:
        return all(known_colour_token(token) for token in tokens.groups())
    return PAINT_VALUE.fullmatch(value) is not None
