from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.core.errors import InvalidInput
from app.research.component_specs_science_geometry import MoleculeGeometry
from app.science.molecule_conformer import conformer_geometry, element_counts, hill_formula, undrawn_elements
from app.science.molecule_drawing import REST_PITCH, REST_YAW, molecule_drawing
from app.science.molecule_elements import DRAWN_ELEMENTS, ELEMENTS, atom_token, key_label

from .compose_held import About, Composition, CraftHeld, HeldCompound, NamedCompound, composed, refused
from .compose_parts import FIGURE, UnitBook, composed_component, joined, key_word, rich_formula

__all__ = [
    "CANDIDATES_MAX",
    "MOLECULES_MAX",
    "NONE_HELD",
    "NO_COMPOUND",
    "SIDE_FACTS_MAX",
    "molecule_3d",
    "molecule_candidates",
]

MOLECULES_MAX = 2
CANDIDATES_MAX = 4
SIDE_FACTS_MAX = 3
SIDE_STYLE = "t-body-sm"
NOTE = "Its 3D conformer is PubChem's record."
CONFORMERS_KEY = "3D conformers computed by PubChem."
TURN_HINT = "Drag, or use the arrow keys, to turn it; plus and minus zoom."
NONE_HELD = (
    "a material of {name} held with its PubChem compound and stated by its own facts, or a compound its facts "
    "name given as about.compound: lookup gives a compound's CID, and propose_facts states what the material "
    "or compound is"
)
NO_MATERIAL = "the material {key}: {slug} holds no material of its own with a PubChem compound under that key"
NO_COMPOUND = (
    "the compound CID {cid}: no material of {slug} is held as that compound and no fact of it names it"
)
NO_CONFORMER = "a 3D conformer for {name} (CID {cid}): PubChem holds none"
UNREAD = "a 3D conformer for {name} (CID {cid}) that this server can read: {problem}"
UNDRAWN = (
    "an atom colour for {elements} in {name} (CID {cid}): the design system colours {drawn} only; ask the "
    "team for the others before a 3D model draws them"
)


@dataclass(frozen=True)
class _Model:
    source: NamedCompound
    geometry: MoleculeGeometry

    @property
    def compound(self) -> HeldCompound:
        return self.source.compound


def molecule_candidates(
    craft: CraftHeld, about: About, named: Sequence[NamedCompound] = ()
) -> tuple[list[NamedCompound], str | None]:
    held = [m for m in craft.materials if m.compound is not None and craft.stated(m.claim_ids)]
    if about.material is not None:
        held = [m for m in held if m.key == about.material]
        if not held:
            return [], NO_MATERIAL.format(key=about.material, slug=craft.slug)
    found = [NamedCompound(m.compound, m.claim_ids) for m in held if m.compound is not None]
    if about.material is None:
        found += [compound for compound in named if craft.stated(compound.claim_ids)]
    if about.compound is not None:
        found = [compound for compound in found if compound.compound.cid == about.compound]
        if not found:
            return [], NO_COMPOUND.format(cid=about.compound, slug=craft.slug)
    if not found:
        return [], NONE_HELD.format(name=craft.name)
    return _first_of_each_compound(found)[:CANDIDATES_MAX], None


def _first_of_each_compound(found: Sequence[NamedCompound]) -> list[NamedCompound]:
    first: dict[int, NamedCompound] = {}
    for source in found:
        first.setdefault(source.compound.cid, source)
    return list(first.values())


def molecule_3d(
    craft: CraftHeld, about: About, conformers: Mapping[int, str | None], named: Sequence[NamedCompound] = ()
) -> Composition:
    candidates, problem = molecule_candidates(craft, about, named)
    if problem is not None:
        return refused(problem)
    models: list[_Model] = []
    gaps: list[str] = []
    for source in candidates:
        model, gap = _model(source, conformers)
        if gap is not None:
            gaps.append(gap)
        elif model is not None and len(models) < MOLECULES_MAX:
            models.append(model)
    if not models:
        return refused(*gaps)
    book = UnitBook()
    return composed(composed_component(craft, _piece(craft, models, book), book), left_out=gaps)


def _model(source: NamedCompound, conformers: Mapping[int, str | None]) -> tuple[_Model | None, str | None]:
    compound = source.compound
    if compound.cid not in conformers:
        return None, None
    sdf = conformers[compound.cid]
    if sdf is None:
        return None, NO_CONFORMER.format(name=compound.name, cid=compound.cid)
    try:
        geometry = conformer_geometry(sdf)
    except InvalidInput as unread:
        return None, UNREAD.format(name=compound.name, cid=compound.cid, problem=unread)
    undrawn = undrawn_elements(geometry)
    if undrawn:
        drawn = joined(list(DRAWN_ELEMENTS))
        return None, UNDRAWN.format(
            elements=joined(undrawn), name=compound.name, cid=compound.cid, drawn=drawn
        )
    return _Model(source, geometry), None


def _piece(craft: CraftHeld, models: Sequence[_Model], book: UnitBook) -> dict[str, Any]:
    names = [model.compound.name for model in models]
    title = f"{joined(names)} in three dimensions"
    facts = _side_facts(craft, models)
    spec = {
        "head": {"figure": None, "number": book.label(FIGURE), "title": book.label(title, facts)},
        "molecules": [_molecule(model) for model in models],
        "side": [
            {"tag": "p", "style": SIDE_STYLE, "unit": book.cited(craft.facts[c].text, [c])} for c in facts
        ],
        "key": _key(models),
    }
    return {
        "name": f"{'-and-'.join(key_word(name) for name in names)}-3d",
        "kind": "molecule_3d",
        "title": title,
        "description": (
            f"Turns {joined(names)} in three dimensions from PubChem's 3D conformer, beside the facts of "
            f"{craft.name} that name {'them' if len(names) > 1 else 'it'}. Place it in the chemistry chapter of the "
            f"page of {craft.name}, by pointer, touch or keyboard."
        ),
        "spec": spec,
    }


def _side_facts(craft: CraftHeld, models: Sequence[_Model]) -> tuple[uuid.UUID, ...]:
    return craft.stated(claim for model in models for claim in model.source.claim_ids)[:SIDE_FACTS_MAX]


def _molecule(model: _Model) -> dict[str, Any]:
    compound, geometry = model.compound, model.geometry
    return {
        "key": f"m{compound.cid}",
        "cid": compound.cid,
        "yaw": REST_YAW,
        "pitch": REST_PITCH,
        "name": compound.name,
        "dialLabel": f"Turn the {compound.name} model",
        "formula": rich_formula(compound.formula) or rich_formula(hill_formula(geometry)),
        "atoms": f"{_atom_words(geometry)}. {TURN_HINT}",
        "note": NOTE,
        "drawing": molecule_drawing(geometry, yaw=REST_YAW, pitch=REST_PITCH),
        "geometry": geometry.model_dump(mode="json"),
    }


def _atom_words(geometry: MoleculeGeometry) -> str:
    counts = element_counts(geometry)
    words = [f"{counts[symbol]} {ELEMENTS[symbol].name}" for symbol in DRAWN_ELEMENTS if symbol in counts]
    return f"{joined(words)} atoms"


def _key(models: Sequence[_Model]) -> list[dict[str, Any]]:
    present = {symbol for model in models for symbol in element_counts(model.geometry)}
    items: list[dict[str, Any]] = [
        {"swatch": atom_token(symbol), "label": key_label(symbol)}
        for symbol in DRAWN_ELEMENTS
        if symbol in present
    ]
    return [*items, {"swatch": None, "label": CONFORMERS_KEY}]
