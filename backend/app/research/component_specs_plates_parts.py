from __future__ import annotations

import re
from collections.abc import Mapping
from types import MappingProxyType
from typing import Annotated, Any, Literal, Self

from pydantic import AfterValidator, ConfigDict, Field, model_validator

from .base import ContractModel, absent, empty
from .craft_parts import Focal
from .depicted_materials import DEPICTED_MATERIALS
from .monograph_page import COMPONENT_LABEL_PATTERN, ITALIC_ROLES, MARK_TAGS
from .unit_ids import UNIT_REF_PATTERN

__all__ = [
    "DRAWING_TAGS",
    "ArtFrame",
    "ClassName",
    "ComponentLabel",
    "DepictedMaterial",
    "DomId",
    "DrawingElement",
    "FileName",
    "HeldOrUnit",
    "HeldText",
    "Picture",
    "UnitRef",
    "ViewBox",
    "held_text",
]

CLASS_PATTERN = r"^[A-Za-z][A-Za-z0-9_-]*$"
DOM_ID_PATTERN = r"^[A-Za-z][A-Za-z0-9_:.-]*$"
PICTURE_PATTERN = (
    r"^(/monographs/[a-z0-9-]+/img/[A-Za-z0-9._-]+\.(jpg|jpeg|png|webp)"
    r"|/api/(crafts/contributed|knowledge/pages/pictures)/"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    r"|https://upload\.wikimedia\.org/wikipedia/commons/[0-9a-f]/[0-9a-f]{2}/[^\s/?#]+)$"
)
DRAWING_ATTRIBUTE = re.compile(r"[A-Za-z][A-Za-z0-9:_-]*")
EVENT_PREFIX = "on"
SHOWN_SOURCE_KEYS = frozenset({"number", "title"})
LOCAL_REFERENCE = "#"
REFERENCE_ATTRIBUTES = ("href", "xlink:href")
SCRIPT_SCHEME = "javascript:"
DRAWING_TAGS = (
    "svg",
    "g",
    "defs",
    "title",
    "desc",
    "path",
    "rect",
    "circle",
    "ellipse",
    "line",
    "polyline",
    "polygon",
    "text",
    "tspan",
    "use",
    "linearGradient",
    "radialGradient",
    "stop",
    "pattern",
    "mask",
    "clipPath",
    "filter",
    "feGaussianBlur",
)
MARK_KEYS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "s": frozenset({"cls", "src", "sid", "pair"}),
        "span": frozenset({"cls"}),
        "cite": frozenset({"key", "g", "shown"}),
        "i": frozenset({"role"}),
        "link": frozenset({"cls", "href", "rel", "target", "ask", "lang"}),
        "figref": frozenset({"ref"}),
        **{mark: frozenset() for mark in MARK_TAGS},
    }
)
NODE_KEYS = frozenset({"m", "c"})
VIEW_BOX_PATTERN = r"^-?\d+(\.\d+)? -?\d+(\.\d+)? \d+(\.\d+)? \d+(\.\d+)?$"
FILE_NAME_PATTERN = r"^[a-z0-9]+(-[a-z0-9]+)*$"

UnitRef = Annotated[str, Field(pattern=UNIT_REF_PATTERN)]
ComponentLabel = Annotated[str, Field(pattern=COMPONENT_LABEL_PATTERN)]
ClassName = Annotated[str, Field(pattern=CLASS_PATTERN)]
DomId = Annotated[str, Field(pattern=DOM_ID_PATTERN)]
ViewBox = Annotated[str, Field(pattern=VIEW_BOX_PATTERN)]
FileName = Annotated[str, Field(pattern=FILE_NAME_PATTERN)]
DepictedMaterial = Literal[*DEPICTED_MATERIALS]


def held_text(nodes: list[Any]) -> list[Any]:
    if not nodes:
        raise ValueError("Held text has at least one node")
    for node in nodes:
        _held_node(node)
    return nodes


HeldText = Annotated[list[Any], AfterValidator(held_text)]
HeldOrUnit = UnitRef | HeldText


class Picture(ContractModel):
    src: str = Field(pattern=PICTURE_PATTERN)
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    alt: str = Field(min_length=1)
    loading: Literal["eager", "lazy"] | None = None
    fetch_priority: Literal["high"] | None = None
    decoding: Literal["sync", "async"] | None = None
    focal: Focal | None = Field(default=None, exclude_if=empty)
    themed: bool | None = Field(default=None, exclude_if=absent)


class ArtFrame(ContractModel):
    symbol: DomId
    view_box: ViewBox
    width: int = Field(ge=1)
    height: int = Field(ge=1)


class DrawingElement(ContractModel):
    model_config = ConfigDict(str_strip_whitespace=False)

    tag: Literal[*DRAWING_TAGS]
    attrs: dict[str, str] = Field(default_factory=dict)
    children: list[DrawingElement | str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _safe_attributes(self) -> Self:
        for name, value in self.attrs.items():
            _drawing_attribute(name, value)
        return self


def _drawing_attribute(name: str, value: str) -> None:
    if not DRAWING_ATTRIBUTE.fullmatch(name) or name.lower().startswith(EVENT_PREFIX):
        raise ValueError(f"No drawing attribute {name!r}")
    if name in REFERENCE_ATTRIBUTES and not value.startswith(LOCAL_REFERENCE):
        raise ValueError(f"A drawing refers only to its page: {name}={value!r}")
    if SCRIPT_SCHEME in "".join(value.split()).lower():
        raise ValueError(f"A drawing attribute runs no script: {name}")


def _held_node(node: Any) -> None:
    if isinstance(node, str):
        return
    if not isinstance(node, dict):
        raise ValueError(f"A held text node is text or a mark, not {node!r}")
    mark = node.get("m")
    allowed = MARK_KEYS.get(mark) if isinstance(mark, str) else None
    if allowed is None:
        raise ValueError(f"No inline mark {mark!r}")
    extra = set(node) - allowed - NODE_KEYS
    if extra:
        raise ValueError(f"The mark {mark} has no {sorted(extra)}")
    _mark_fields(mark, node)
    children = node.get("c", [])
    if not isinstance(children, list):
        raise ValueError(f"The mark {mark} holds a list of nodes")
    for child in children:
        _held_node(child)


def _mark_fields(mark: str, node: Mapping[str, Any]) -> None:
    if mark == "cite":
        _cite(node)
    elif mark == "link" and not node.get("href"):
        raise ValueError("A link has an href")
    elif mark == "i" and node.get("role") not in (None, *ITALIC_ROLES):
        raise ValueError(f"No italic role {node.get('role')!r}")
    elif mark == "figref" and not node.get("ref"):
        raise ValueError("A figure reference names its figure")


def _cite(node: Mapping[str, Any]) -> None:
    keys, shown = node.get("g"), node.get("shown")
    if not node.get("key") or not isinstance(keys, list) or not keys:
        raise ValueError("A citation has a key and its sources")
    if not isinstance(shown, list) or not shown:
        raise ValueError("A held citation shows its numbered sources")
    if any(not isinstance(entry, dict) or set(entry) != SHOWN_SOURCE_KEYS for entry in shown):
        raise ValueError("A shown source is its number and title")
    numbers = [entry["number"] for entry in shown]
    if any(not isinstance(number, int) or number < 1 for number in numbers):
        raise ValueError("A shown source has a number from 1")
    if numbers != sorted(set(numbers)):
        raise ValueError("A citation shows each source number once, in order")
    if any(not isinstance(entry["title"], str) or not entry["title"] for entry in shown):
        raise ValueError("A shown source has its title")
