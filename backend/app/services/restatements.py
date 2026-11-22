from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from app.data.craft_text import fold
from app.research.quotes import content_stem, content_stems, numbers_in
from app.research.sentence_support import figure_units

__all__ = [
    "NEAR_VERBATIM_SHARE",
    "PASSAGE_RUN_WORDS",
    "RESTATED_STEMS_MIN",
    "SAME_FIGURES_SHARE",
    "SAME_GROUP_SHARE",
    "SAME_PASSAGE_SHARE",
    "Said",
    "restates",
    "restates_any",
    "said",
]

RESTATED_STEMS_MIN = 4
SAME_GROUP_SHARE = 0.5
SAME_FIGURES_SHARE = 0.5
SAME_PASSAGE_SHARE = 0.3
PASSAGE_RUN_WORDS = 6
NEAR_VERBATIM_SHARE = 0.8
NEGATION = re.compile(r"\b(not|no|never|neither|nor|without|cannot)\b")
WORD = re.compile(r"\w+")


@dataclass(frozen=True)
class Said:
    stems: frozenset[str]
    numbers: frozenset[str]
    negated: bool
    claims: frozenset[str]
    evidence: frozenset[tuple[str, str]]
    figures: frozenset[tuple[str, str]] = frozenset()

    @property
    def subject(self) -> frozenset[str]:
        return self.stems - {content_stem(unit) for _, unit in self.figures}


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
        figures=frozenset((number, unit.casefold()) for number, unit in figure_units(text)),
    )


def restates(later: Said, earlier: Said) -> bool:
    if len(later.stems) < RESTATED_STEMS_MIN or later.negated != earlier.negated:
        return False
    if not later.numbers <= earlier.numbers:
        return False
    share = _share(later.stems, earlier.stems)
    if _same_group(later, earlier):
        return share >= SAME_GROUP_SHARE
    if _same_passage(later, earlier) and share >= SAME_PASSAGE_SHARE:
        return True
    if _same_figures(later, earlier) and _share(later.subject, earlier.subject) >= SAME_FIGURES_SHARE:
        return True
    return later.numbers == earlier.numbers and share >= NEAR_VERBATIM_SHARE


def restates_any(later: Said, shown: Iterable[Said]) -> bool:
    return any(restates(later, earlier) for earlier in shown)


def _share(later: frozenset[str], earlier: frozenset[str]) -> float:
    joined = later | earlier
    return len(later & earlier) / len(joined) if joined else 0.0


def _same_group(later: Said, earlier: Said) -> bool:
    by_claims = bool(later.claims) and later.claims <= earlier.claims
    by_evidence = bool(later.evidence) and later.evidence <= earlier.evidence
    return by_claims or by_evidence


def _same_figures(later: Said, earlier: Said) -> bool:
    return bool(later.numbers) and later.numbers == earlier.numbers and later.figures == earlier.figures


def _same_passage(later: Said, earlier: Said) -> bool:
    return bool(later.evidence) and all(
        any(source == other and _overlapping(quote, passage) for other, passage in earlier.evidence)
        for source, quote in later.evidence
    )


def _overlapping(quote: str, passage: str) -> bool:
    if quote and passage and (quote in passage or passage in quote):
        return True
    return bool(_word_runs(quote) & _word_runs(passage))


def _word_runs(text: str) -> set[tuple[str, ...]]:
    words = WORD.findall(text)
    return {tuple(words[n : n + PASSAGE_RUN_WORDS]) for n in range(len(words) - PASSAGE_RUN_WORDS + 1)}
