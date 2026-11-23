from __future__ import annotations

import re
from collections.abc import Sequence

from app.research.crafts import CraftRef

from .drafting import DraftQuery, PlanDraft

__all__ = [
    "COLOURANT_ELEMENTS",
    "MINERAL_SURFACES",
    "asks_what_gives_a_colour",
    "colourant_queries",
    "colourant_text",
]

COLOURANT_ELEMENTS = ("cobalt", "copper", "iron", "manganese", "chromium")
COLOUR_WORDS = frozenset(
    {"colour", "colours", "color", "colors", "coloured", "colored", "hue", "hues", "tint"}
)
HUES = (
    "blue",
    "turquoise",
    "green",
    "red",
    "yellow",
    "black",
    "brown",
    "white",
    "pink",
    "purple",
    "violet",
    "grey",
    "gray",
    "ochre",
    "maroon",
)
MINERAL_SURFACES = frozenset(
    {
        "glaze",
        "glazes",
        "glazed",
        "glass",
        "enamel",
        "enamels",
        "enamelled",
        "pigment",
        "pigments",
        "ceramic",
        "ceramics",
        "pottery",
        "porcelain",
        "stoneware",
        "earthenware",
        "tile",
        "tiles",
        "faience",
    }
)
ASKS_A_CAUSE = re.compile(
    r"\b(?:what|which)\b.*\b(?:gives?|makes?|produces?|creates?|causes?)\b"
    r"|\bwhere\b.*\bcomes?\b|\bhow\b.*\b(?:colou?red|gets?|made)\b",
    re.IGNORECASE,
)
MATERIAL_FACET = "MATERIAL"
WORD = re.compile(r"[^\W_]+")


def asks_what_gives_a_colour(question: str, craft: CraftRef | None) -> bool:
    words = {word.casefold() for word in WORD.findall(question)}
    named = words | ({word.casefold() for word in WORD.findall(craft.name)} if craft else set())
    coloured = bool(words & COLOUR_WORDS) or any(hue in words for hue in HUES)
    return coloured and bool(named & MINERAL_SURFACES) and ASKS_A_CAUSE.search(question) is not None


def colourant_text(question: str) -> str:
    words = {word.casefold() for word in WORD.findall(question)}
    named_hues = [hue for hue in HUES if hue in words]
    oxides = " ".join(f"{element} oxide" for element in COLOURANT_ELEMENTS)
    return " ".join([*named_hues, "glaze colourant", oxides])


def colourant_queries(
    question: str, craft: CraftRef | None, draft: PlanDraft, facet_indexes: Sequence[int]
) -> list[DraftQuery]:
    if not facet_indexes or not asks_what_gives_a_colour(question, craft):
        return []
    facet = next((i for i in facet_indexes if draft.facets[i].type == MATERIAL_FACET), facet_indexes[0])
    tiers = list(dict.fromkeys(query.tier for query in draft.queries)) or ["T3"]
    return [DraftQuery(facet_index=facet, tier=tier, text=colourant_text(question)) for tier in tiers]
