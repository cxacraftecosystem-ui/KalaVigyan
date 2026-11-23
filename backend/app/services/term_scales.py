from __future__ import annotations

import re
import uuid
from collections.abc import Iterable, Mapping
from types import MappingProxyType

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Term
from app.models.enums import TERM_ZOOM_LEVELS

__all__ = ["COMPOUND_LEVEL", "SCALE_WORDS", "fill_zoom_levels", "scale_stripped", "stated_zoom_level"]

COMPOUND_LEVEL = "MOLECULE"
SCALE_WORDS: Mapping[str, frozenset[str]] = MappingProxyType(
    {
        "WORKSHOP": frozenset({"workshop", "workshops"}),
        "CLOTH": frozenset({"cloth", "cloths", "fabric", "fabrics", "textile", "textiles"}),
        "FIBRE": frozenset({"fibre", "fibres", "fiber", "fibers"}),
        "MOLECULE": frozenset({"molecule", "molecules", "compound", "compounds"}),
    }
)
WORD = re.compile(r"[^\W\d_]+")


def stated_zoom_level(label: str, meaning: str | None) -> str | None:
    by_head = _levels(_words(label)[-1:])
    if len(by_head) == 1:
        return by_head.pop()
    stated = _levels(_words(meaning or ""))
    return stated.pop() if len(stated) == 1 else None


def scale_stripped(label: str, level: str) -> str:
    words = label.split()
    if len(words) > 1 and words[-1].casefold() in SCALE_WORDS[level]:
        return " ".join(words[:-1])
    return label


async def fill_zoom_levels(session: AsyncSession) -> int:
    rows = await session.execute(
        select(Term.id, Term.label, Term.meaning).where(Term.zoomLevel.is_(None)).order_by(Term.id)
    )
    stated = _stated_levels(rows.tuples().all())
    for level in TERM_ZOOM_LEVELS:
        ids = [term_id for term_id, found in stated.items() if found == level]
        if ids:
            await session.execute(update(Term).where(Term.id.in_(ids)).values(zoomLevel=level))
    return len(stated)


def _stated_levels(rows: Iterable[tuple[uuid.UUID, str, str | None]]) -> dict[uuid.UUID, str]:
    found = {term_id: stated_zoom_level(label, meaning) for term_id, label, meaning in rows}
    return {term_id: level for term_id, level in found.items() if level is not None}


def _words(text: str) -> list[str]:
    return WORD.findall(text.casefold())


def _levels(words: Iterable[str]) -> set[str]:
    found = set(words)
    return {level for level in TERM_ZOOM_LEVELS if found & SCALE_WORDS[level]}
