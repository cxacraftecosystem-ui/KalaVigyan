from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

__all__ = [
    "CLOTH_FORMS",
    "EARTH",
    "FAMILIES",
    "HEAT_SOURCES",
    "KIT_MOTIONS",
    "KIT_PARTS",
    "KIT_VERSION",
    "LAYERS_MAX",
    "LAYERS_MIN",
    "LAYOUTS",
    "MOTIFS",
    "PANELS_PER_LAYOUT",
    "PARTS_PER_PANEL_MAX",
    "PASTE_FORMS",
    "PIECE_SHAPES",
    "SPECIES_MARKS",
    "SPECIES_PER_SCENE_MAX",
    "SPECIES_ROLES",
    "TOOLS",
    "VESSELS",
    "WATER_FORMS",
    "KitPart",
    "choice_named",
    "kit_vocabulary",
    "parts_named_by",
]

KIT_VERSION = 1
FAMILIES = ("textiles", "metal", "clay", "stone", "wood", "leather", "fibre", "paper", "more")
MOTIFS = ("star", "lattice", "dots", "lines")
CLOTH_FORMS = ("swatch", "length", "folded")
VESSELS = ("vat", "pot", "trough", "pit")
PASTE_FORMS = ("spread", "printed", "outline")
HEAT_SOURCES = ("sun", "fire", "furnace", "lamp")
WATER_FORMS = ("running", "still", "sprinkled")
TOOLS = ("block", "brush", "chisel", "mallet", "knife", "stick")
PIECE_SHAPES = ("lump", "vessel", "slab", "billet", "sheet", "figure", "culm")
SPECIES_ROLES = ("reactant", "reagent", "product")
SPECIES_MARKS = ("clear", "gas", "ion")
KIT_MOTIONS = ("dip", "take", "dry", "react")
EARTH = "earth"
PARTS_PER_PANEL_MAX = 3
SPECIES_PER_SCENE_MAX = 8
LAYERS_MIN = 2
LAYERS_MAX = 6
LAYOUTS = ("steps", "before_after", "section", "sequence")
PANELS_PER_LAYOUT: Mapping[str, tuple[int, int]] = MappingProxyType(
    {"steps": (2, 6), "before_after": (2, 2), "section": (1, 1), "sequence": (2, 6)}
)
WORD = re.compile(r"[a-z]+")


@dataclass(frozen=True)
class KitPart:
    name: str
    families: tuple[str, ...]
    subjects: tuple[str, ...]
    choices: Mapping[str, tuple[str, ...]]
    materials: tuple[str, ...]
    motion: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "families": list(self.families),
            "subjects": list(self.subjects),
            "choices": {name: list(values) for name, values in self.choices.items()},
            "materials": list(self.materials),
            "motion": self.motion,
        }


def _part(name: str, families: tuple[str, ...], subjects: str, **rest: Any) -> KitPart:
    return KitPart(
        name=name,
        families=families,
        subjects=tuple(subjects.split()),
        choices=MappingProxyType(rest.get("choices", {})),
        materials=rest.get("materials", ()),
        motion=rest.get("motion"),
    )


KIT_PARTS: Mapping[str, KitPart] = MappingProxyType(
    {
        part.name: part
        for part in (
            _part(
                "cloth",
                ("textiles", "more"),
                "cloth cotton fabric textile swatch",
                choices={"form": CLOTH_FORMS, "printed.motif": MOTIFS},
                materials=("material", "printed.material"),
                motion="take",
            ),
            _part(
                "block",
                ("textiles", "wood"),
                "block blocks stamp",
                choices={"motif": MOTIFS},
                materials=("paste",),
            ),
            _part(
                "bath",
                ("textiles", "metal", "leather", "fibre", "paper"),
                "vat vats bath baths liquor",
                choices={"vessel": VESSELS},
                materials=("liquor", "piece"),
                motion="dip",
            ),
            _part(
                "paste",
                ("textiles", "metal", "paper", "more"),
                "paste mordant resist",
                choices={"form": PASTE_FORMS},
                materials=("material", "on", "dried"),
                motion="dry",
            ),
            _part(
                "heat",
                ("textiles", "metal", "clay", "wood", "fibre", "paper", "more"),
                "sun fire furnace kiln flame",
                choices={"source": HEAT_SOURCES},
            ),
            _part(
                "water",
                ("textiles", "metal", "leather", "fibre", "paper"),
                "water washing rinse rinsing",
                choices={"form": WATER_FORMS},
            ),
            _part(
                "tool",
                ("textiles", "metal", "stone", "wood", "fibre", "paper", "more"),
                "hand hands chisel mallet brush",
                choices={"tool": TOOLS},
                materials=("load",),
            ),
            _part(
                "section",
                ("textiles", "metal", "clay", "leather", "more"),
                "section cutaway strata layers",
                materials=("layers.material",),
            ),
            _part(
                "piece",
                ("metal", "clay", "stone", "wood", "fibre", "paper", "more"),
                "slab billet lump",
                choices={"shape": PIECE_SHAPES, "inlay.motif": MOTIFS},
                materials=("material", "inlay.material"),
            ),
            _part(
                "species",
                FAMILIES,
                "species reactant reactants reagent reagents",
                choices={"role": SPECIES_ROLES, "mark": SPECIES_MARKS},
                materials=("material",),
                motion="react",
            ),
        )
    }
)


def kit_vocabulary() -> dict[str, Any]:
    return {
        "version": KIT_VERSION,
        "families": list(FAMILIES),
        "layouts": {name: list(PANELS_PER_LAYOUT[name]) for name in LAYOUTS},
        "partsPerPanelMax": PARTS_PER_PANEL_MAX,
        "speciesPerSceneMax": SPECIES_PER_SCENE_MAX,
        "layers": [LAYERS_MIN, LAYERS_MAX],
        "earth": EARTH,
        "motions": list(KIT_MOTIONS),
        "motifs": list(MOTIFS),
        "parts": {name: part.as_dict() for name, part in KIT_PARTS.items()},
    }


def parts_named_by(text: str) -> list[tuple[str, str]]:
    words = WORD.findall(text.casefold())
    found: dict[str, str] = {}
    for word in words:
        for part in KIT_PARTS.values():
            if word in part.subjects and part.name not in found:
                found[part.name] = word
    return list(found.items())


def choice_named(part: str, choice: str, text: str) -> str | None:
    words = set(WORD.findall(text.casefold()))
    values = KIT_PARTS[part].choices.get(choice, ())
    return next((value for value in values if value in words or f"{value}s" in words), None)
