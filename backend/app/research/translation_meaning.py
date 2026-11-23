from __future__ import annotations

from .hedges import hedges_in
from .quotes import QUOTE_OVERLAP_MIN, content_stems
from .stance_markers import negation_marked
from .translation import translation_problems
from .vocabulary import CANONICAL_LANGUAGE

__all__ = [
    "READ_BACK_TERMS_KEPT_MIN",
    "READ_BACK_TERMS_MIN",
    "TRANSLATION_CHECKS_EDITION",
    "meaning_problems",
]

TRANSLATION_CHECKS_EDITION = "read-back-1"
READ_BACK_TERMS_MIN = 3
READ_BACK_TERMS_KEPT_MIN = QUOTE_OVERLAP_MIN
ADDED_NEGATION = "it adds a negation the English does not have"
ADDED_HEDGE = "it adds a hedge the English does not have"


def meaning_problems(english: str, read_back: str) -> list[str]:
    problems = translation_problems(english, read_back, language=CANONICAL_LANGUAGE)
    if negation_marked(read_back, CANONICAL_LANGUAGE) and not negation_marked(english, CANONICAL_LANGUAGE):
        problems.append(ADDED_NEGATION)
    if hedges_in(read_back) and not hedges_in(english):
        problems.append(ADDED_HEDGE)
    return problems + _terms_problems(english, read_back)


def _terms_problems(english: str, read_back: str) -> list[str]:
    asked = content_stems(english)
    if len(asked) < READ_BACK_TERMS_MIN:
        return []
    lost = asked - content_stems(read_back)
    kept = len(asked) - len(lost)
    if kept / len(asked) >= READ_BACK_TERMS_KEPT_MIN:
        return []
    return [f"it keeps {kept} of the English's {len(asked)} terms; lost: {', '.join(sorted(lost))}"]
