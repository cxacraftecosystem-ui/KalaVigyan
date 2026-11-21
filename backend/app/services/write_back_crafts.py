from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass

from app.data.craft_master_loader import load_master
from app.data.craft_text import STOP_TOKENS, ascii_key
from app.research.crafts import CraftRef

__all__ = [
    "ANCHOR_MIN_CHARS",
    "COMMON_NAME_USES",
    "SKIP_SEVERAL_CRAFTS",
    "CraftFiling",
    "craft_filing",
    "named_crafts",
]

ANCHOR_MIN_CHARS = 4
COMMON_NAME_USES = 3
SKIP_SEVERAL_CRAFTS = "names more than one of the compared crafts, so no one craft's page can hold it"


@dataclass(frozen=True)
class CraftFiling:
    slug: str | None
    refused: str | None = None


def craft_filing(text: str, lead: CraftRef | None, compared: Sequence[CraftRef]) -> CraftFiling:
    lead_slug = lead.slug if lead is not None else None
    if not compared:
        return CraftFiling(lead_slug)
    named = named_crafts(text, [craft for craft in (lead, *compared) if craft is not None])
    if len(named) > 1:
        return CraftFiling(None, SKIP_SEVERAL_CRAFTS)
    return CraftFiling(named[0].slug if named else lead_slug)


def named_crafts(text: str, crafts: Sequence[CraftRef]) -> list[CraftRef]:
    words = set(ascii_key(text).split())
    common = _common_name_words()
    return [craft for craft in crafts if _anchors(craft, crafts, common) & words]


def _anchors(craft: CraftRef, crafts: Sequence[CraftRef], common: frozenset[str]) -> set[str]:
    shared = {word for other in crafts if other.slug != craft.slug for word in _words(other.name)}
    return {
        word
        for word in _words(craft.name)
        if len(word) >= ANCHOR_MIN_CHARS and word not in STOP_TOKENS | common | shared
    }


def _common_name_words() -> frozenset[str]:
    uses = Counter(word for master in load_master() for word in set(_words(master.name)))
    return frozenset(word for word, count in uses.items() if count >= COMMON_NAME_USES)


def _words(name: str) -> list[str]:
    return ascii_key(name).split()
