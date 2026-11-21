from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.core.errors import ExternalFailure

__all__ = ["RERANK_SERVICE", "Relevance", "Reranker", "checked_relevance"]

RERANK_SERVICE = "rerank"


@dataclass(frozen=True)
class Relevance:
    index: int
    score: float


class Reranker(Protocol):
    async def __call__(self, query: str, documents: Sequence[str]) -> list[Relevance]: ...


def checked_relevance(found: Sequence[Relevance], *, documents: int) -> list[Relevance]:
    seen: set[int] = set()
    for item in found:
        if not 0 <= item.index < documents or item.index in seen:
            raise ExternalFailure(
                f"The rerank route returned index {item.index} for {documents} documents",
                service=RERANK_SERVICE,
            )
        if not math.isfinite(item.score):
            raise ExternalFailure(
                "The rerank route returned a score that is not a number", service=RERANK_SERVICE
            )
        seen.add(item.index)
    return sorted(found, key=lambda item: (-item.score, item.index))
