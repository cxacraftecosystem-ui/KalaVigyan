from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any

from .compose_held import (
    About,
    Composition,
    CraftHeld,
    HeldReaction,
    HeldSpecies,
    HeldStage,
    composed,
    refused,
)
from .compose_parts import (
    FIGURE,
    UnitBook,
    composed_component,
    joined,
    material_named,
    rich_formula,
    species_token,
    unique_word,
)
from .compose_scene import reaction_scene, species_drawn, species_mark, species_scene

__all__ = ["REACTION_WORDS", "STEPS_MAX", "reaction_player"]

STEPS_MAX = 12
STEPS_MIN = 2
LANE = "Species in this step"
TIME_TERM = "Time"
NO_EQUATION = "Named as the sources name it, without an equation."
CLEAR = "clear"
REACTION_WORDS = {
    "REDOX": "Redox",
    "ACID_BASE": "Acid and base",
    "COMPLEXATION": "Complexation",
    "PRECIPITATION": "Precipitation",
    "DEHYDRATION": "Dehydration",
    "DEHYDROXYLATION": "Dehydroxylation",
    "PHASE_CHANGE": "Change of phase",
    "POLYMERISATION": "Polymerisation",
    "HYDROLYSIS": "Hydrolysis",
    "OTHER": "Change",
}
NO_REACTIONS = (
    "two reactions stated by {name}'s own facts: propose_structure REACTION items for {slug}, each with the "
    "stage_key it happens in and the quotes that name its reactants and products"
)
ONE_REACTION = (
    "a second reaction stated by {name}'s own facts, since a player steps through two or more: {slug} holds "
    "only {key}; propose_structure REACTION with its stage_key"
)
NO_KEY = "the reaction {key}: {slug} holds no reaction of its own under that key"
UNSTATED = "a fact of {slug}'s own for the reaction {key}, which rests on no fact the page shows"

Played = tuple[HeldReaction, HeldStage | None]


def reaction_player(craft: CraftHeld, about: About) -> Composition:
    played, unstated = _played(craft, about)
    problem = _problem(craft, about, played)
    if problem is not None:
        return refused(problem, *unstated)
    book = UnitBook()
    names: list[str] = []
    steps = [_step(craft, entry, book, names) for entry in played]
    _drawn_steps(craft, played, steps, book)
    return composed(
        composed_component(craft, _piece(craft, played, steps, about, book), book), left_out=unstated
    )


def _piece(
    craft: CraftHeld, played: Sequence[Played], steps: list[dict[str, Any]], about: About, book: UnitBook
) -> dict[str, Any]:
    current = _current(played, about)
    title = f"The reactions of {craft.name}, step by step"
    rest = played[current - 1][0]
    spec = {
        "id": f"rp-{craft.label_root()}",
        "track": "reactions",
        "head": {
            "figure": None,
            "number": book.label(FIGURE),
            "title": book.label(title, _claims(craft, played)),
        },
        "current": current,
        "steps": steps,
        "scenes": [] if all(step["scene"] for step in steps) else [reaction_scene(craft, played, current)],
        "key": None,
        "status": book.label(_heading(rest), craft.stated(rest.claim_ids)),
    }
    return {
        "name": "reactions-step-by-step",
        "kind": "reaction_player",
        "title": title,
        "description": (
            f"Steps through the reactions {craft.name}'s own facts state, in the order of its stages, each with "
            f"its species, its equation where the server balanced one and the facts that state it. Place it in "
            f"the chemistry chapter of the page of {craft.name}."
        ),
        "spec": spec,
    }


def _played(craft: CraftHeld, about: About) -> tuple[list[Played], list[str]]:
    order = {stage.key: at for at, stage in enumerate(craft.stages)}
    held = [
        reaction for reaction in craft.reactions if about.stage is None or reaction.stage_key == about.stage
    ]
    stated = [reaction for reaction in held if craft.stated(reaction.claim_ids)]
    unstated = [UNSTATED.format(slug=craft.slug, key=r.key) for r in held if not craft.stated(r.claim_ids)]
    ordered = sorted(stated, key=lambda r: (order.get(r.stage_key or "", len(order)), r.key))
    return [(reaction, craft.stage(reaction.stage_key)) for reaction in ordered][:STEPS_MAX], unstated


def _problem(craft: CraftHeld, about: About, played: Sequence[Played]) -> str | None:
    keys = [reaction.key for reaction, _ in played]
    if about.reaction is not None and about.reaction not in keys:
        return NO_KEY.format(key=about.reaction, slug=craft.slug)
    if not played:
        return NO_REACTIONS.format(name=craft.name, slug=craft.slug)
    if len(played) < STEPS_MIN:
        return ONE_REACTION.format(name=craft.name, slug=craft.slug, key=keys[0])
    return None


def _current(played: Sequence[Played], about: About) -> int:
    keys = [reaction.key for reaction, _ in played]
    return keys.index(about.reaction) + 1 if about.reaction in keys else len(keys)


def _claims(craft: CraftHeld, played: Sequence[Played]) -> tuple[uuid.UUID, ...]:
    return craft.stated(claim for reaction, _ in played for claim in reaction.claim_ids)


def _step(craft: CraftHeld, entry: Played, book: UnitBook, names: list[str]) -> dict[str, Any]:
    reaction, stage = entry
    claims = craft.stated(reaction.claim_ids)
    name = _rail_name(reaction, stage, names)
    names.append(name)
    text = {
        "kicker": book.label(REACTION_WORDS.get(reaction.kind, REACTION_WORDS["OTHER"])),
        "heading": book.label(_heading(reaction), claims),
        "paragraphs": [book.cited(craft.facts[claim].text, [claim]) for claim in claims],
        "bond": None,
        "link": None,
        "conditions": _conditions(craft, stage, book),
        "differs": None,
    }
    chemistry = {"parts": [_lane(craft, reaction), _equation(reaction, book)]}
    return {"name": name, "text": text, "chemistry": chemistry, "scene": None}


def _drawn_steps(
    craft: CraftHeld, played: Sequence[Played], steps: list[dict[str, Any]], book: UnitBook
) -> None:
    if not all(species_drawn(reaction) for reaction, _ in played):
        return
    for step, (reaction, stage) in zip(steps, played, strict=True):
        where = (
            book.label(stage.name, craft.stated(stage.claim_ids))
            if stage is not None
            else book.label(step["name"], craft.stated(reaction.claim_ids))
        )
        step["scene"] = {"where": where, "art": species_scene(craft, reaction, book)}


def _rail_name(reaction: HeldReaction, stage: HeldStage | None, taken: Sequence[str]) -> str:
    name = stage.name if stage is not None else reaction.products[0].name
    if name in taken:
        name = f"{name}: {reaction.products[0].name}"
    while name in taken:
        name = f"{name} ({unique_word(reaction.key, ())})"
    return name


def _heading(reaction: HeldReaction) -> str:
    said = f"{joined([s.name for s in reaction.reactants])} to {joined([s.name for s in reaction.products])}"
    return said[:1].upper() + said[1:]


def _conditions(craft: CraftHeld, stage: HeldStage | None, book: UnitBook) -> list[dict[str, str]]:
    timing = stage.duration if stage is not None else None
    if timing is None or not craft.stated([timing.claim_id]):
        return []
    return [{"term": book.label(TIME_TERM), "value": book.cited(timing.text, [timing.claim_id])}]


def _lane(craft: CraftHeld, reaction: HeldReaction) -> dict[str, Any]:
    items = _side(craft, reaction.reactants)
    items.append(
        {"item": "arrow", "label": REACTION_WORDS.get(reaction.kind, REACTION_WORDS["OTHER"]).lower()}
    )
    items += _side(craft, reaction.products)
    return {"part": "lane", "label": LANE, "items": items}


def _side(craft: CraftHeld, species: Sequence[HeldSpecies]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for at, each in enumerate(species):
        if at:
            items.append({"item": "plus"})
        material = material_named(craft, each.name)
        compound = material.compound if material is not None else None
        items.append(
            {
                "item": "species",
                "swatch": species_token(craft, each.name) or species_mark(each) or CLEAR,
                "name": [each.name],
                "formula": rich_formula(each.formula),
                "state": [],
                "cid": compound.cid if compound is not None else None,
            }
        )
    return items


def _equation(reaction: HeldReaction, book: UnitBook) -> dict[str, Any]:
    species = [*reaction.reactants, *reaction.products]
    coefficients = reaction.coefficients
    if coefficients is None or len(coefficients) != len(species) or any(not s.formula for s in species):
        return {"part": "none", "unit": book.label(NO_EQUATION)}
    terms = [_term(each, count) for each, count in zip(species, coefficients, strict=True)]
    names = [joined([s.name for s in side]) for side in (reaction.reactants, reaction.products)]
    line = {"reactants": terms[: len(reaction.reactants)], "products": terms[len(reaction.reactants) :]}
    equation = {
        "label": f"{names[0]} gives {names[1]}",
        "style": None,
        "line": line,
        "atoms": None,
        "notes": [],
    }
    return {"part": "equation", "equation": equation}


def _term(species: HeldSpecies, count: int) -> dict[str, Any]:
    runs = rich_formula(species.formula) or [species.name]
    if count > 1:
        first = runs[0]
        runs = [f"{count} {first}", *runs[1:]] if isinstance(first, str) else [f"{count} ", *runs]
    return {"formula": runs, "name": species.name}
