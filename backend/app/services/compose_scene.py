from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from app.research.art_kit import SPECIES_PER_SCENE_MAX

from .compose_held import CraftHeld, HeldReaction, HeldSpecies, HeldStage
from .compose_parts import UnitBook, material_named, species_token

__all__ = ["reaction_scene", "species_drawn", "species_mark", "species_scene"]

SCENE_WIDTH = 640
SCENE_HEIGHT = 180
SCENE_MARGIN = 40
SWATCH_MAX = 64
SWATCH_GAP = 12
ARROW_WIDTH = 72
OFF = "off"
INK = "var(--ink-2)"
ARROW_INK = "var(--ink-3)"
GROUND = "var(--sunk)"
OUTLINE_FILL = "var(--raised)"
UNRECORDED_DASH = "6 4"

SPECIES_PART = "species"
REACTANT, REAGENT, PRODUCT = "reactant", "reagent", "product"
REACT = "react"
OXYGEN_WORD = "oxygen"
OXYGEN_FORMULA = "O2"
WATER_WORD = "water"
WATER_FORMULA = "H2O"
GAS_FORMULAS = frozenset({"O2", "H2", "N2", "CO2"})
ION_WORDS = frozenset({"ion", "ions"})
CHARGES = ("+", "-")
CLEAR_MARK, GAS_MARK, ION_MARK = "clear", "gas", "ion"
MORDANT_ROLE = "MORDANT"
AGENT_WORDS = frozenset({"alum", "aluminium", "aluminum", "iron", "ferrous", "ferric", "mordant"})
BREAKING_KINDS = frozenset({"HYDROLYSIS", "DEHYDRATION", "DEHYDROXYLATION"})
WORD = re.compile(r"[a-z]+")

Node = dict[str, Any]
Played = tuple[HeldReaction, HeldStage | None]


def species_drawn(reaction: HeldReaction) -> bool:
    count = len(reaction.reactants) + len(reaction.products)
    return bool(reaction.reactants) and 0 < count <= SPECIES_PER_SCENE_MAX


def species_scene(craft: CraftHeld, reaction: HeldReaction, book: UnitBook) -> Node:
    claims = craft.stated(reaction.claim_ids)
    breaking = _breaking(reaction)
    arriving = _arriving(craft, reaction.reactants) - {breaking}
    parts = [
        _species(
            craft,
            species,
            book,
            role=REAGENT if at in arriving else REACTANT,
            breaks=at == breaking,
            claims=claims,
        )
        for at, species in enumerate(reaction.reactants)
    ]
    parts += [
        _species(craft, species, book, role=PRODUCT, breaks=False, claims=claims)
        for species in reaction.products
    ]
    return {"parts": parts, **({"motion": REACT} if reaction.products else {})}


def _species(
    craft: CraftHeld, species: HeldSpecies, book: UnitBook, *, role: str, breaks: bool, claims: Sequence[Any]
) -> Node:
    part: Node = {"part": SPECIES_PART, "role": role, "label": book.cited(species.name, claims)}
    token = species_token(craft, species.name)
    mark = species_mark(species)
    if token is not None:
        part["material"] = token
    elif mark is not None:
        part["mark"] = mark
    if breaks:
        part["breaks"] = True
    return part


def species_mark(species: HeldSpecies) -> str | None:
    if _oxygen(species) or _formula(species) in GAS_FORMULAS:
        return GAS_MARK
    if _water(species):
        return CLEAR_MARK
    if _formula(species).endswith(CHARGES) or ION_WORDS & _words(species.name):
        return ION_MARK
    return None


def _arriving(craft: CraftHeld, reactants: Sequence[HeldSpecies]) -> set[int]:
    for found in (_oxygen, lambda species: _agent(craft, species)):
        chosen = {at for at, species in enumerate(reactants) if found(species)}
        if chosen and len(chosen) < len(reactants):
            return chosen
    return set()


def _breaking(reaction: HeldReaction) -> int | None:
    reactants = reaction.reactants
    if len(reactants) == 1 and len(reaction.products) > 1:
        return 0
    if reaction.kind not in BREAKING_KINDS:
        return None
    return next((at for at, species in enumerate(reactants) if not _water(species)), None)


def _oxygen(species: HeldSpecies) -> bool:
    return _formula(species) == OXYGEN_FORMULA or OXYGEN_WORD in _words(species.name)


def _water(species: HeldSpecies) -> bool:
    return _formula(species) == WATER_FORMULA or _words(species.name) == {WATER_WORD}


def _agent(craft: CraftHeld, species: HeldSpecies) -> bool:
    material = material_named(craft, species.name)
    return (material is not None and material.role == MORDANT_ROLE) or bool(
        AGENT_WORDS & _words(species.name)
    )


def _formula(species: HeldSpecies) -> str:
    return "".join((species.formula or "").split())


def _words(text: str) -> set[str]:
    return set(WORD.findall(text.casefold()))


def reaction_scene(craft: CraftHeld, played: Sequence[Played], current: int) -> Node:
    groups = [
        _step_group(craft, reaction, step, current) for step, (reaction, _) in enumerate(played, start=1)
    ]
    attrs = {
        "class": "scene",
        "viewBox": f"0 0 {SCENE_WIDTH} {SCENE_HEIGHT}",
        "aria-hidden": "true",
        "focusable": "false",
    }
    ground = _rect(0, 0, (SCENE_WIDTH, SCENE_HEIGHT), {"fill": GROUND})
    return {"tag": "svg", "attrs": attrs, "children": [ground, *groups]}


def _step_group(craft: CraftHeld, reaction: HeldReaction, step: int, current: int) -> Node:
    sides = (reaction.reactants, reaction.products)
    count = len(sides[0]) + len(sides[1])
    room = SCENE_WIDTH - 2 * SCENE_MARGIN - ARROW_WIDTH - SWATCH_GAP * (count - 1)
    size = min(SWATCH_MAX, room / count)
    top = (SCENE_HEIGHT - size) / 2
    x = (SCENE_WIDTH - (count * size + SWATCH_GAP * (count - 1) + ARROW_WIDTH)) / 2
    children: list[Node] = []
    for at, side in enumerate(sides):
        for species in side:
            children.append(_swatch(craft, species, (x, top), size))
            x += size + SWATCH_GAP
        if at == 0:
            children += _arrow(x - SWATCH_GAP / 2, SCENE_HEIGHT / 2)
            x += ARROW_WIDTH
    attrs = {"data-on": str(step)} | ({} if step == current else {"class": OFF})
    return {"tag": "g", "attrs": attrs, "children": children}


def _swatch(craft: CraftHeld, species: HeldSpecies, at: tuple[float, float], size: float) -> Node:
    material = material_named(craft, species.name)
    paint = {"fill": OUTLINE_FILL, "stroke": INK, "stroke-width": "1.5"}
    if (material is None or not material.tokens) and species_mark(species) is None:
        paint["stroke-dasharray"] = UNRECORDED_DASH
    return _rect(at[0], at[1], (size, size), {"rx": "4", **paint})


def _arrow(x: float, y: float) -> list[Node]:
    start, end = x + 12, x + ARROW_WIDTH - 12
    line = {
        "x1": _n(start),
        "y1": _n(y),
        "x2": _n(end - 8),
        "y2": _n(y),
        "stroke": ARROW_INK,
        "stroke-width": "2",
    }
    head = f"{_n(end)},{_n(y)} {_n(end - 10)},{_n(y - 6)} {_n(end - 10)},{_n(y + 6)}"
    return [{"tag": "line", "attrs": line}, {"tag": "polygon", "attrs": {"points": head, "fill": ARROW_INK}}]


def _rect(x: float, y: float, size: tuple[float, float], paint: dict[str, str]) -> Node:
    box = {"x": _n(x), "y": _n(y), "width": _n(size[0]), "height": _n(size[1])}
    return {"tag": "rect", "attrs": box | paint}


def _n(value: float) -> str:
    rounded = round(value, 1)
    return str(int(rounded)) if rounded == int(rounded) else str(rounded)
