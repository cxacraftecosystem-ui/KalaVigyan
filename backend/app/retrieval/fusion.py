from __future__ import annotations

import math
from collections.abc import Hashable, Iterable, Sequence
from dataclasses import dataclass

from app.core.errors import InvalidInput

__all__ = ["EQUAL_WEIGHT", "RRF_K", "VOTING_DEPTH", "FusedItem", "fused_order", "reciprocal_rank_fusion"]

RRF_K = 60
VOTING_DEPTH = 30
EQUAL_WEIGHT = 1.0


@dataclass(frozen=True)
class FusedItem[K: Hashable]:
    key: K
    score: float
    ranks: tuple[int | None, ...]
    voted: float

    @property
    def best_rank(self) -> int:
        return min(rank for rank in self.ranks if rank is not None)


def reciprocal_rank_fusion[K: Hashable](
    rankings: Sequence[Sequence[K]],
    *,
    k: int = RRF_K,
    voting_depth: int = VOTING_DEPTH,
    weights: Sequence[float] | None = None,
) -> list[FusedItem[K]]:
    if k <= 0:
        raise InvalidInput(f"The fusion constant must be positive, not {k}")
    if voting_depth <= 0:
        raise InvalidInput(f"A ranking votes with at least its first item, not {voting_depth}")
    weighted = _checked_weights(weights, len(rankings))
    positions = [_positions(index, ranking) for index, ranking in enumerate(rankings)]
    keys = {key for found in positions for key in found}
    fused = [
        _fused(key, tuple(found.get(key) for found in positions), weighted, k=k, voting_depth=voting_depth)
        for key in keys
    ]
    return sorted(fused, key=fused_order)


def fused_order[K: Hashable](item: FusedItem[K]) -> tuple[float, float, int, str]:
    return (-item.voted, -item.score, item.best_rank, str(item.key))


def _checked_weights(weights: Sequence[float] | None, rankings: int) -> tuple[float, ...]:
    if weights is None:
        return (EQUAL_WEIGHT,) * rankings
    if len(weights) != rankings:
        raise InvalidInput(f"{len(weights)} weights were given for {rankings} rankings")
    if any(not math.isfinite(weight) or weight < 0 for weight in weights) or not any(weights):
        raise InvalidInput(
            f"Each ranking's weight is a finite number of zero or more, one above zero: {weights}"
        )
    return tuple(weights)


def _fused[K: Hashable](
    key: K, ranks: tuple[int | None, ...], weights: tuple[float, ...], *, k: int, voting_depth: int
) -> FusedItem[K]:
    found = [(rank, weight) for rank, weight in zip(ranks, weights, strict=True) if rank is not None]
    voting = [(rank, weight) for rank, weight in found if rank <= voting_depth]
    return FusedItem(key=key, score=_summed(found, k=k), ranks=ranks, voted=_summed(voting, k=k))


def _summed(ranks: Iterable[tuple[int, float]], *, k: int) -> float:
    return sum((weight / (k + rank) for rank, weight in ranks), 0.0)


def _positions[K: Hashable](index: int, ranking: Sequence[K]) -> dict[K, int]:
    found: dict[K, int] = {}
    for rank, key in enumerate(ranking, start=1):
        if key in found:
            raise InvalidInput(f"Ranking {index} lists {key!r} twice")
        found[key] = rank
    return found
