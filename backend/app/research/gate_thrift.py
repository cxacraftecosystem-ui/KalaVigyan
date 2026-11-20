from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

from .candidate_gates import DUPLICATE_GATE, NOVELTY_GATE, Candidate, GateOutcome, HeldFact
from .quotes import content_stems, figures_in

__all__ = [
    "NOVELTY_JUDGE_SIMILARITY",
    "TWIN_STEM_OVERLAP",
    "VECTOR_TWIN_SIMILARITY",
    "GateThrift",
    "distant_novelty",
    "novel_by_distance",
    "vector_twin",
    "vector_twin_outcome",
]

VECTOR_TWIN_SIMILARITY = 0.97
TWIN_STEM_OVERLAP = 0.8
NOVELTY_JUDGE_SIMILARITY = 0.75
NEGATION = re.compile(r"\b(?:not|no|never|none|nor|neither|without|cannot)\b|n't\b", re.IGNORECASE)


@dataclass(frozen=True)
class GateThrift:
    twin_similarity: float = VECTOR_TWIN_SIMILARITY
    novelty_similarity: float = NOVELTY_JUDGE_SIMILARITY


def vector_twin(statement: str, close: Sequence[HeldFact], *, at_least: float) -> HeldFact | None:
    ranked = sorted(close, key=lambda fact: (-fact.similarity, str(fact.id)))
    return next(
        (fact for fact in ranked if fact.similarity >= at_least and _same_claim(statement, fact.text)), None
    )


def vector_twin_outcome(twin: HeldFact) -> GateOutcome:
    reason = (
        f"fact {twin.id} already says it in nearly the same words, with the same figures and no negation "
        f"between them (similarity {twin.similarity:.2f}), so no judge was asked"
    )
    return GateOutcome(gate=DUPLICATE_GATE, passed=False, reasons=[reason], related=[twin.id])


def novel_by_distance(nearest: Sequence[HeldFact], *, below: float) -> bool:
    return bool(nearest) and all(fact.similarity < below for fact in nearest)


def distant_novelty(candidate: Candidate, nearest: Sequence[HeldFact]) -> GateOutcome:
    closest = max(fact.similarity for fact in nearest)
    where = f"in {candidate.field}" if candidate.field else "in any field"
    reason = (
        f"no held fact {where} comes near it (the nearest at similarity {closest:.2f}), so it adds to the "
        "section and no judge was asked"
    )
    return GateOutcome(gate=NOVELTY_GATE, passed=True, reasons=[reason])


def _same_claim(statement: str, held: str) -> bool:
    if sorted(figures_in(statement)) != sorted(figures_in(held)):
        return False
    if _negations(statement) != _negations(held):
        return False
    return _stem_overlap(statement, held) >= TWIN_STEM_OVERLAP


def _negations(text: str) -> list[str]:
    return sorted(found.casefold() for found in NEGATION.findall(text))


def _stem_overlap(first: str, second: str) -> float:
    left, right = content_stems(first), content_stems(second)
    if not left and not right:
        return 1.0
    return len(left & right) / len(left | right)
