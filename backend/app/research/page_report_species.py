from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from typing import Any

__all__ = ["UNCOLOURED", "UNMATCHED", "species_colour_problems"]

SPECIES = "species"
CLEAR = "clear"
MARKS = frozenset({CLEAR, "gas", "ion"})
UNCOLOURED = (
    "{label}, {where}: its scene draws {names} with no colour, each an empty outline; give each species "
    "part material, the depicted material its facts state (Kutch Ajrakh draws alizarin in --dye-madder and "
    "harda's tannin in --dye-harda), or mark clear, gas or ion for a colourless substance, and give its lane "
    "the same swatch, in the draft with edit_draft"
)
UNMATCHED = (
    "{label}, {where}: its lane marks '{name}' clear, an empty dashed square, while its scene draws it in "
    "{material}; give the lane's swatch {material}, in the draft with edit_draft"
)

Text = Callable[[str], str]


def species_colour_problems(label: str, spec: Mapping[str, Any], text: Text) -> list[str]:
    found: list[str] = []
    for where, parts, lane in _scenes(spec):
        drawn: dict[str, str] = {}
        empty: list[str] = []
        for part in parts:
            name = text(str(part.get("label") or "")).strip() or SPECIES
            colour = part.get("material") or part.get("mark")
            if colour:
                drawn[name.casefold()] = str(colour)
            else:
                empty.append(f"'{name}'")
        if empty:
            found.append(UNCOLOURED.format(label=label, where=where, names=", ".join(empty)))
        found += [
            UNMATCHED.format(label=label, where=where, name=name, material=drawn[name.casefold()])
            for name, swatch in lane
            if swatch == CLEAR and drawn.get(name.casefold(), CLEAR) not in MARKS
        ]
    return found


def _scenes(spec: Mapping[str, Any]) -> Iterator[tuple[str, list[Mapping[str, Any]], list[tuple[str, str]]]]:
    steps = spec.get("steps")
    if isinstance(steps, list):
        for at, step in enumerate(steps, start=1):
            if isinstance(step, Mapping):
                art = _mapping(_mapping(step.get("scene")).get("art"))
                yield f"step {at} ({step.get('name')})", _species(art.get("parts")), _lane(step)
        return
    for at, panel in enumerate(_list(spec.get("panels")), start=1):
        yield f"panel {at}", _species(_mapping(panel).get("parts")), []


def _species(parts: Any) -> list[Mapping[str, Any]]:
    return [part for part in _list(parts) if isinstance(part, Mapping) and part.get("part") == SPECIES]


def _lane(step: Mapping[str, Any]) -> list[tuple[str, str]]:
    chemistry = _mapping(step.get("chemistry"))
    return [
        (_runs(item.get("name")), str(item.get("swatch")))
        for part in _list(chemistry.get("parts"))
        for item in _list(_mapping(part).get("items"))
        if isinstance(item, Mapping) and item.get("item") == SPECIES
    ]


def _runs(value: Any) -> str:
    runs = value if isinstance(value, list) else [value]
    return "".join(
        run if isinstance(run, str) else str(_mapping(run).get("text") or "") for run in runs
    ).strip()


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []
