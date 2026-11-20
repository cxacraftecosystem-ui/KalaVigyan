from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass

from .crafts import CraftRef

__all__ = [
    "FIELDS_FOR_FULL_STANDING",
    "FOUND_MAX",
    "GENERIC_WORDS",
    "KNOWLEDGE_WEIGHT",
    "LEXICAL_WEIGHT",
    "NAMED_IN_FULL_BONUS",
    "PLACE_SCORE",
    "STANDING_WEIGHT",
    "CraftSignals",
    "ScoredCraft",
    "covered_words",
    "finder_score",
    "query_words",
    "ranked_crafts",
    "standing_score",
]

LEXICAL_WEIGHT = 0.55
KNOWLEDGE_WEIGHT = 0.30
STANDING_WEIGHT = 0.15
PLACE_SCORE = 0.6
NAMED_IN_FULL_BONUS = 0.1
EXACT_LEXICAL = 0.95
STEM_CHARS = 4
FOUND_MAX = 5
QUERY_WORDS_MAX = 8
WORD_MIN_CHARS = 3
FIELDS_FOR_FULL_STANDING = 16
COVERED_FLOOR = 0.5
SCORE_DIGITS = 6
WORD = re.compile(r"[a-z0-9]+")
GENERIC_WORDS = frozenset(
    {
        "and",
        "are",
        "art",
        "arts",
        "craft",
        "crafts",
        "for",
        "from",
        "handicraft",
        "handicrafts",
        "how",
        "india",
        "indian",
        "made",
        "the",
        "traditional",
        "what",
        "which",
        "who",
        "why",
        "with",
        "work",
    }
)


@dataclass(frozen=True)
class CraftSignals:
    craft: CraftRef
    lexical: float = 0.0
    named_words: frozenset[str] = frozenset()
    held_words: frozenset[str] = frozenset()
    held_hits: int = 0
    curated: bool = False
    claims: int = 0
    fields: int = 0


@dataclass(frozen=True)
class ScoredCraft:
    signals: CraftSignals
    score: float


def query_words(text: str) -> tuple[str, ...]:
    found = [word for word in WORD.findall(text.casefold()) if len(word) >= WORD_MIN_CHARS]
    kept = [word for word in dict.fromkeys(found) if word not in GENERIC_WORDS]
    return tuple(kept[:QUERY_WORDS_MAX])


def standing_score(signals: CraftSignals) -> float:
    if signals.curated:
        return 1.0
    if signals.claims == 0:
        return 0.0
    spread = min(1.0, signals.fields / FIELDS_FOR_FULL_STANDING)
    return COVERED_FLOOR + (1.0 - COVERED_FLOOR) * spread


def covered_words(words: Sequence[str], tokens: Iterable[str]) -> set[str]:
    held = tuple(tokens)
    return {word for word in words if any(_same_word(word, token) for token in held)}


def finder_score(signals: CraftSignals, words: Sequence[str]) -> float:
    wanted = set(words)
    named = len(covered_words(words, signals.named_words)) / len(wanted) if wanted else 1.0
    held = len(signals.held_words & wanted) / len(wanted) if wanted else 0.0
    in_full = named == 1.0 and signals.lexical >= EXACT_LEXICAL
    score = (
        LEXICAL_WEIGHT * signals.lexical * named
        + (NAMED_IN_FULL_BONUS if in_full else 0.0)
        + KNOWLEDGE_WEIGHT * held
        + STANDING_WEIGHT * standing_score(signals)
    )
    return round(min(1.0, score), SCORE_DIGITS)


def ranked_crafts(signals: Sequence[CraftSignals], words: Sequence[str]) -> list[ScoredCraft]:
    found = [ScoredCraft(item, finder_score(item, words)) for item in signals if _relevant(item, words)]
    return sorted(
        found,
        key=lambda scored: (
            -scored.score,
            not scored.signals.curated,
            -scored.signals.claims,
            scored.signals.craft.name.casefold(),
            scored.signals.craft.slug,
        ),
    )[:FOUND_MAX]


def _relevant(signals: CraftSignals, words: Sequence[str]) -> bool:
    if not words:
        return signals.lexical > 0
    return bool(covered_words(words, signals.named_words)) or bool(signals.held_words & set(words))


def _same_word(word: str, token: str) -> bool:
    if word == token:
        return True
    return len(word) >= STEM_CHARS and len(token) >= STEM_CHARS and word[:STEM_CHARS] == token[:STEM_CHARS]
