from __future__ import annotations

import math
import re
from collections.abc import Iterator
from dataclasses import dataclass
from xml.etree import ElementTree

from .drawing_roles import MATERIAL_ROLES, PAINT_PROPERTIES, css_declarations, paint_problem, paint_roles

__all__ = [
    "DRAWN_WIDTH_MIN",
    "PROBLEMS_SHOWN",
    "TEXT_FLOOR_PX",
    "drawing_problems",
    "listed",
    "local_name",
    "text_floor",
]

TEXT_FLOOR_PX = 12
DRAWN_WIDTH_MIN = 320
DEFAULT_FONT_SIZE = 16.0
PROBLEMS_SHOWN = 6
MASKS = frozenset({"mask", "clipPath"})
TEXTS = frozenset({"text", "tspan", "textPath"})
GRADIENTS = frozenset({"linearGradient", "radialGradient"})
RETIRED_FILTERS = frozenset({"feGaussianBlur", "feDropShadow", "feMorphology"})
FONT_NAMES = frozenset({"font-family", "font"})
TYPE_PROPERTIES = frozenset(
    {"font-family", "font", "font-size", "font-weight", "line-height", "letter-spacing"}
)
SIZE = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(px)?\s*$")
TRANSFORM = re.compile(r"(scale|matrix)\(([^)]*)\)")
NUMBER = re.compile(r"-?\d+(?:\.\d+)?(?:e-?\d+)?")
GLYPH_ID = re.compile(r"glyph|^dejavu|^cm(r|mi|sy|ex)\d", re.IGNORECASE)
LOCAL_URL = re.compile(r"^url\(#([\w.-]+)\)$")


@dataclass(frozen=True)
class Context:
    masked: bool
    size: float
    scale: float
    molecules: bool


def local_name(tag: object) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def listed(problems: list[str]) -> str:
    shown = "; ".join(problems[:PROBLEMS_SHOWN])
    more = len(problems) - PROBLEMS_SHOWN
    return f"{shown}; and {more} more" if more > 0 else shown


def text_floor(view_width: float) -> float:
    return TEXT_FLOOR_PX * view_width / DRAWN_WIDTH_MIN


def drawing_problems(root: ElementTree.Element, view_width: float, *, molecules: bool = False) -> list[str]:
    gradients = _gradient_roles(root)
    floor = text_floor(view_width)
    found: list[str] = []
    start = Context(masked=False, size=DEFAULT_FONT_SIZE, scale=1.0, molecules=molecules)
    for element, context in _walk(root, start):
        found += _element_problems(element, context)
        found += _text_problems(element, context, floor, gradients)
    found += _gradient_problems(gradients)
    return list(dict.fromkeys(found))


def _walk(element: ElementTree.Element, context: Context) -> Iterator[tuple[ElementTree.Element, Context]]:
    here = Context(
        masked=context.masked or local_name(element.tag) in MASKS,
        size=_font_size(element) or context.size,
        scale=context.scale * _transform_scale(element.get("transform", "")),
        molecules=context.molecules,
    )
    yield element, here
    for child in element:
        yield from _walk(child, here)


def _named(element: ElementTree.Element) -> str:
    tag = local_name(element.tag)
    identity = element.get("id")
    return f'the <{tag} id="{identity}">' if identity else f"a <{tag}>"


def _element_problems(element: ElementTree.Element, context: Context) -> list[str]:
    tag = local_name(element.tag)
    named = _named(element)
    found: list[str] = []
    for name, value in _properties(element):
        if name in FONT_NAMES:
            found.append(f"{named} names a font; its text is set in the design's UI face")
        elif name in PAINT_PROPERTIES and (
            problem := paint_problem(value, in_mask=context.masked, molecules=context.molecules)
        ):
            found.append(f"{named}'s {name} {problem}")
        elif name == "font-size" and _font_size_of(value) is None:
            found.append(f"{named} sizes its text as {value!r}; give the font size in drawing units")
    if tag in RETIRED_FILTERS:
        found.append(f"{named} blurs or casts a shadow, a retired look; draw it flat")
    if _outlined_text(element):
        found.append(f"{named} draws words as outlines; set every word as a <text> element")
    return found


def _properties(element: ElementTree.Element) -> Iterator[tuple[str, str]]:
    for name, value in element.attrib.items():
        if name == "style":
            yield from css_declarations(value)
        elif not name.startswith("{"):
            yield name.casefold(), value
    if local_name(element.tag) == "style" and element.text:
        yield from css_declarations(element.text)


def _text_problems(
    element: ElementTree.Element, context: Context, floor: float, gradients: dict[str, list[str]]
) -> list[str]:
    if local_name(element.tag) not in TEXTS or not (element.text or "").strip():
        return []
    words = " ".join((element.text or "").split())[:40]
    found: list[str] = []
    drawn = context.size * context.scale
    if drawn + 1e-9 < floor:
        found.append(
            f"the text '{words}' is drawn at {drawn * TEXT_FLOOR_PX / floor:.1f} px when the drawing is "
            f"{DRAWN_WIDTH_MIN} px wide, under the {TEXT_FLOOR_PX} px floor; set it at "
            f"{math.ceil(floor / context.scale)} units or more"
        )
    fill = dict(_properties(element)).get("fill", "")
    reference = LOCAL_URL.match(" ".join(fill.split()))
    if reference and reference.group(1) in gradients:
        found.append(f"the text '{words}' is filled with a gradient, a retired look; give it one role")
    return found


def _gradient_roles(root: ElementTree.Element) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    for element in root.iter():
        if local_name(element.tag) in GRADIENTS and element.get("id"):
            stops = [stop for stop in element.iter() if local_name(stop.tag) == "stop"]
            roles = [role for stop in stops for _, value in _paints(stop) for role in paint_roles(value)]
            found[str(element.get("id"))] = roles
    return found


def _paints(element: ElementTree.Element) -> Iterator[tuple[str, str]]:
    return ((name, value) for name, value in _properties(element) if name in PAINT_PROPERTIES)


def _gradient_problems(gradients: dict[str, list[str]]) -> list[str]:
    found: list[str] = []
    for identity, roles in gradients.items():
        kinds = {_ramp(role) for role in roles if role not in MATERIAL_ROLES}
        if len(kinds) > 1:
            found.append(
                f'the gradient "{identity}" blends {" and ".join(sorted(set(roles)))}, a retired look; a gradient '
                "fades one role, steps through one ramp or passes between depicted materials"
            )
    return found


def _ramp(role: str) -> str:
    stem, _, step = role.rpartition("-")
    return stem if step.isdigit() and stem not in ("ink",) else role


def _font_size(element: ElementTree.Element) -> float | None:
    sizes = [_font_size_of(value) for name, value in _properties(element) if name == "font-size"]
    known = [size for size in sizes if size is not None]
    return known[-1] if known else None


def _font_size_of(value: str) -> float | None:
    found = SIZE.match(value)
    return float(found.group(1)) if found else None


def _transform_scale(transform: str) -> float:
    scale = 1.0
    for kind, arguments in TRANSFORM.findall(transform):
        numbers = [float(number) for number in NUMBER.findall(arguments)]
        if kind == "scale" and numbers:
            scale *= math.sqrt(abs(numbers[0] * (numbers[1] if len(numbers) > 1 else numbers[0])))
        elif kind == "matrix" and len(numbers) >= 4:
            scale *= math.sqrt(abs(numbers[0] * numbers[3] - numbers[1] * numbers[2]))
    return scale


def _outlined_text(element: ElementTree.Element) -> bool:
    if GLYPH_ID.search(element.get("id", "")):
        return True
    if not element.get("aria-label", "").strip() or local_name(element.tag) not in ("g", "path"):
        return False
    typeset = any(name in TYPE_PROPERTIES for name, _ in _properties(element))
    paths = [child for child in element.iter() if local_name(child.tag) == "path"]
    words = [child for child in element.iter() if local_name(child.tag) in TEXTS]
    return typeset and bool(paths) and not words
