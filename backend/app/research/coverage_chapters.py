from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from app.models.enums import DISCIPLINES

from .chapter_keys import CHAPTER_KEYS

__all__ = ["FIELD_CHAPTERS", "field_chapter"]

FIELD_CHAPTERS: Mapping[str, str] = MappingProxyType(
    {
        "OVERVIEW": "glance",
        "PROCESS": "made",
        "CHEMISTRY": "chem",
        "PHYSICS": "chem",
        "MATERIALS": "made",
        "GEOGRAPHY": "why",
        "GEOLOGY": "why",
        "CLIMATE": "why",
        "ECOLOGY": "why",
        "BOTANY": "chem",
        "HISTORY": "history",
        "ECONOMICS": "market",
        "DESIGN": "people",
        "HEALTH": "made",
        "SOCIETY": "people",
        "POLICY": "market",
    }
)

if tuple(FIELD_CHAPTERS) != DISCIPLINES or not set(FIELD_CHAPTERS.values()) <= set(CHAPTER_KEYS):
    raise RuntimeError("every field is placed once, in a chapter of the page")


def field_chapter(discipline: str) -> str:
    return FIELD_CHAPTERS[discipline]
