from __future__ import annotations

from dataclasses import dataclass

from .structured import StructuredModel

__all__ = ["JudgeLadder"]


@dataclass(frozen=True)
class JudgeLadder:
    first: StructuredModel
    escalate: tuple[StructuredModel, ...] = ()

    @property
    def models(self) -> tuple[StructuredModel, ...]:
        return (self.first, *self.escalate)
