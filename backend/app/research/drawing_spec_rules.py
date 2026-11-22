from __future__ import annotations

import re
from collections.abc import Iterator, Mapping
from typing import Any
from xml.etree import ElementTree

from .component_specs_general_svg import sanitised_svg, svg_view_box
from .component_specs_science_parts import SVG_TAGS
from .drawing_roles import MATERIAL_ROLES, role_problem
from .drawing_rules import drawing_problems

__all__ = ["MATERIAL_KEYS", "THEMES_KEY", "drawing_nodes", "spec_design_problems"]

MATERIAL_KEYS = frozenset({"swatch", "dips"})
THEMES_KEY = "themes"
SVG_KEY = "svg"
TOKEN = re.compile(r"^--([a-z0-9-]+)$")
NODE_TAGS = frozenset(SVG_TAGS)


def spec_design_problems(spec: Mapping[str, Any]) -> list[str]:
    found: list[str] = []
    markup = spec.get(SVG_KEY)
    if isinstance(markup, str):
        found += _markup_problems(markup)
    for node in drawing_nodes(spec):
        found += _node_problems(node)
    for path, token, material in _tokens(spec, "", False):
        found += _token_problems(path, token, material)
    return list(dict.fromkeys(found))


def drawing_nodes(value: Any) -> Iterator[Mapping[str, Any]]:
    if isinstance(value, Mapping):
        if value.get("tag") in NODE_TAGS:
            yield value
            return
        for key, item in value.items():
            if key != THEMES_KEY:
                yield from drawing_nodes(item)
    elif isinstance(value, list):
        for item in value:
            yield from drawing_nodes(item)


def _markup_problems(markup: str) -> list[str]:
    try:
        root = ElementTree.fromstring(sanitised_svg(markup))
    except ValueError, ElementTree.ParseError:
        return ["the drawing is not one well-formed SVG drawing"]
    box = svg_view_box(root.get("viewBox"))
    return drawing_problems(root, box[2] if box else 0.0)


def _node_problems(node: Mapping[str, Any]) -> list[str]:
    root = _element(node)
    box = svg_view_box(root.get("viewBox")) if root.tag == "svg" else None
    return drawing_problems(root, box[2] if box else 0.0, molecules=True)


def _element(node: Mapping[str, Any]) -> ElementTree.Element:
    attrs = node.get("attrs") or {}
    element = ElementTree.Element(str(node.get("tag")), {str(k): str(v) for k, v in attrs.items()})
    children = node.get("children") or []
    element.text = "".join(child for child in children if isinstance(child, str)) or None
    for child in children:
        if isinstance(child, Mapping):
            element.append(_element(child))
    return element


def _tokens(value: Any, path: str, material: bool) -> Iterator[tuple[str, str, bool]]:
    if isinstance(value, Mapping):
        if value.get("tag") in NODE_TAGS:
            return
        for key, item in value.items():
            if key not in (THEMES_KEY, SVG_KEY):
                yield from _tokens(item, f"{path}.{key}" if path else key, material or key in MATERIAL_KEYS)
    elif isinstance(value, list):
        for at, item in enumerate(value):
            yield from _tokens(item, f"{path}[{at}]", material)
    elif isinstance(value, str) and (found := TOKEN.match(value)):
        yield path, found.group(1), material


def _token_problems(path: str, token: str, material: bool) -> list[str]:
    if material and token not in MATERIAL_ROLES:
        return [f"{path} names --{token}; a swatch or dip shows a depicted --dye-* or --dip-* material"]
    problem = role_problem(token, molecules=True)
    return [f"{path}: {problem}"] if problem else []
