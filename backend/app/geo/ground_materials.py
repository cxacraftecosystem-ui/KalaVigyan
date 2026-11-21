from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from app.research.place_ground import MaterialDeposits

from .ground_layers import Deposit

__all__ = [
    "COMMODITY_TERMS",
    "MATCHED_KINDS",
    "SOIL_KINDS",
    "SOIL_TERMS",
    "CraftMaterial",
    "material_commodities",
    "material_deposits",
    "soil_materials",
]

IRON = ("Iron",)
COPPER = ("Copper",)
ALUMINIUM = ("Aluminum",)
CALCIUM = ("Calcium",)
SILICA = ("Silica",)
SODA = ("Soda Ash", "Sodium Sulfate")
CLAY = ("Clay", "Kaolin")
STONE = ("Stone, Dimension", "Marble")
COMMODITY_TERMS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        "iron": IRON,
        "ochre": IRON,
        "ocher": IRON,
        "haematite": IRON,
        "hematite": IRON,
        "geru": IRON,
        "copper": COPPER,
        "bronze": COPPER,
        "bell metal": COPPER,
        "brass": ("Copper", "Zinc"),
        "zinc": ("Zinc",),
        "lead": ("Lead",),
        "tin": ("Tin",),
        "silver": ("Silver",),
        "gold": ("Gold",),
        "alum": ALUMINIUM,
        "bauxite": ALUMINIUM,
        "aluminium": ALUMINIUM,
        "aluminum": ALUMINIUM,
        "quicklime": CALCIUM,
        "slaked lime": CALCIUM,
        "lime plaster": CALCIUM,
        "limestone": CALCIUM,
        "chalk": CALCIUM,
        "marble": STONE,
        "sandstone": STONE,
        "granite": STONE,
        "silica": SILICA,
        "quartz": SILICA,
        "sand": SILICA,
        "soda ash": SODA,
        "sodium carbonate": SODA,
        "rock salt": ("Halite",),
        "common salt": ("Halite",),
        "gypsum": ("Gypsum-Anhydrite",),
        "graphite": ("Graphite",),
        "manganese": ("Manganese",),
        "chromium": ("Chromium",),
        "borax": ("Boron-Borates",),
        "sulphur": ("Sulfur",),
        "sulfur": ("Sulfur",),
        "mica": ("Mica",),
        "garnet": ("Garnet",),
        "kaolin": CLAY,
        "china clay": CLAY,
        "clay": CLAY,
        "barytes": ("Barium-Barite",),
        "barite": ("Barium-Barite",),
        "magnesite": ("Magnesite",),
        "arsenic": ("Arsenic",),
        "antimony": ("Antimony",),
    }
)
MATCHED_KINDS = frozenset({"MINERAL", "CLAY", "METAL", "MORDANT", "OTHER"})
SOIL_KINDS = frozenset({"CLAY"})
SOIL_TERMS = ("clay", "terracotta", "earth", "mud", "silt", "loam")
TERM_PATTERNS = tuple(
    (re.compile(rf"\b{re.escape(term)}\b"), commodities)
    for term, commodities in sorted(COMMODITY_TERMS.items(), key=lambda item: (-len(item[0]), item[0]))
)
SOIL_PATTERN = re.compile(rf"\b({'|'.join(SOIL_TERMS)})\b")


@dataclass(frozen=True)
class CraftMaterial:
    name: str
    kind: str


def material_commodities(material: CraftMaterial) -> tuple[str, ...]:
    if material.kind not in MATCHED_KINDS:
        return ()
    text = material.name.casefold()
    found: list[str] = []
    for pattern, commodities in TERM_PATTERNS:
        if pattern.search(text):
            found.extend(commodity for commodity in commodities if commodity not in found)
    return tuple(found)


def soil_materials(materials: Iterable[CraftMaterial]) -> list[str]:
    named = (
        material.name
        for material in materials
        if material.kind in SOIL_KINDS or SOIL_PATTERN.search(material.name.casefold())
    )
    return sorted(set(named), key=str.casefold)


def _matching(found: Sequence[tuple[Deposit, float]], commodities: tuple[str, ...]) -> list[float]:
    wanted = set(commodities)
    return [distance for deposit, distance in found if wanted & set(deposit.commodities)]


def material_deposits(
    materials: Iterable[CraftMaterial], found: Sequence[tuple[Deposit, float]]
) -> list[MaterialDeposits]:
    matched: list[MaterialDeposits] = []
    for material in sorted(set(materials), key=lambda item: item.name.casefold()):
        commodities = material_commodities(material)
        distances = _matching(found, commodities) if commodities else []
        if distances:
            matched.append(
                MaterialDeposits(
                    material=material.name,
                    commodities=list(commodities),
                    count=len(distances),
                    nearest_km=round(min(distances), 1),
                )
            )
    return matched
