from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from app.data.craft_text import fold
from app.research.quotes import content_stems, numbers_in

__all__ = [
    "NEAR_VERBATIM_SHARE",
    "RESTATED_STEMS_MIN",
    "SAME_GROUP_SHARE",
    "Said",
    "restates",
    "restates_any",
    "said",
]

RESTATED_STEMS_MIN = 4
SAME_GROUP_SHARE = 0.5
NEAR_VERBATIM_SHARE = 0.8
NEGATION = re.compile(r"\b(not|no|never|neither|nor|without|cannot)\b")


@dataclass(frozen=True)
class Said:
    stems: frozenset[str]
    numbers: frozenset[str]
    negated: bool
    claims: frozenset[str]
    evidence: frozenset[tuple[str, str]]


def said(sentence: Mapping[str, Any]) -> Said:
    text = sentence.get("original") or sentence["text"]
    citations = sentence.get("citations", [])
    return Said(
        stems=frozenset(content_stems(text)),
        numbers=frozenset(numbers_in(text)),
        negated=bool(NEGATION.search(fold(text))),
        claims=frozenset(citation["claimId"] for citation in citations),
        evidence=frozenset(
            (citation["sourceId"], fold(citation["quote"])) for citation in citations if citation.get("quote")
        ),
    )


def restates(later: Said, earlier: Said) -> bool:
    if len(later.stems) < RESTATED_STEMS_MIN or later.negated != earlier.negated:
        return False
    if not later.numbers <= earlier.numbers:
        return False
    share = len(later.stems & earlier.stems) / len(later.stems | earlier.stems)
    if _same_group(later, earlier):
        return share >= SAME_GROUP_SHARE
    return later.numbers == earlier.numbers and share >= NEAR_VERBATIM_SHARE


def restates_any(later: Said, shown: Iterable[Said]) -> bool:
    return any(restates(later, earlier) for earlier in shown)


def _same_group(later: Said, earlier: Said) -> bool:
    by_claims = bool(later.claims) and later.claims <= earlier.claims
    by_evidence = bool(later.evidence) and later.evidence <= earlier.evidence
    return by_claims or by_evidence
