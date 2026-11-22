from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Self

from app.research.sections import SectionSpec

__all__ = ["ASKED", "THIN", "UNASKED", "UNASKED_SENTENCES_DIVISOR", "SectionFields"]

THIN = 2
ASKED = 1
UNASKED = 0
UNASKED_SENTENCES_DIVISOR = 2


@dataclass(frozen=True)
class SectionFields:
    asked: frozenset[str] = frozenset()
    held: frozenset[str] = frozenset()
    shown: frozenset[str] = frozenset()

    @classmethod
    def of(cls, asked: Iterable[str], held: Iterable[str], specs: Iterable[SectionSpec]) -> Self:
        return cls(frozenset(asked), frozenset(held), frozenset(spec.discipline for spec in specs))

    def is_asked(self, discipline: str) -> bool:
        return not self.asked or discipline in self.asked

    def is_thin(self, discipline: str) -> bool:
        return self.is_asked(discipline) and discipline not in self.held

    def priority(self, discipline: str) -> int:
        if self.is_thin(discipline):
            return THIN
        return ASKED if self.is_asked(discipline) else UNASKED

    def sentences_max(self, discipline: str, limit: int) -> int:
        return limit if self.is_asked(discipline) else max(1, limit // UNASKED_SENTENCES_DIVISOR)
