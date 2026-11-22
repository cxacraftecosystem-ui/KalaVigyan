from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from typing import Any

from .component_specs_general import GENERAL_DRAWING
from .drawing_spec_rules import THEMES_KEY, spec_design_problems
from .unit_ids import DELIVERED_UNITS

__all__ = ["DESIGN_RULE", "THEME_NAMES", "delivered", "design_evidence"]

DESIGN_RULE = 27
THEME_NAMES = frozenset({"light", "dark", "hcLight", "hcDark"})
ALT_KEY = "alt"
PICTURE_KEY = "picture"


def delivered(units: Sequence[str]) -> bool:
    return any(DELIVERED_UNITS.holds(unit) for unit in units)


def design_evidence(
    figures: Sequence[tuple[str, str]],
    specs: Mapping[str, Mapping[str, Any]],
    held: Callable[[str], list[str]],
    text: Callable[[str], str],
    pictures: Sequence[str],
) -> list[str]:
    found: list[str] = []
    for label, kind in figures:
        if delivered(held(label)):
            found += _figure_problems(label, kind, specs.get(label, {}), text)
    for label in pictures:
        picture = specs.get(label, {}).get(PICTURE_KEY) or {}
        if not str(picture.get(ALT_KEY) or "").strip():
            found.append(f"{label} has no alt text saying what the picture shows")
    return found


def _figure_problems(label: str, kind: str, spec: Mapping[str, Any], text: Callable[[str], str]) -> list[str]:
    found = [f"{label}: {problem}" for problem in spec_design_problems(spec)]
    if kind != GENERAL_DRAWING:
        return found
    themes = spec.get(THEMES_KEY)
    if not isinstance(themes, Mapping) or set(themes) != THEME_NAMES:
        found.append(f"{label} is a drawing without its light, dark and high-contrast variants")
    if not text(str(spec.get(ALT_KEY) or "")):
        found.append(f"{label} is a drawing with no alt text saying what it shows")
    return found
