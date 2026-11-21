from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable, Sequence

from app.research.planning import RetrievalPlan
from app.research.quotes import content_stems, normalise_quote_text

__all__ = [
    "PASSAGES_PER_DOCUMENT",
    "PASSAGE_MAX_CHARS",
    "best_passages",
    "passage_terms",
    "passages_of",
]

PASSAGE_MAX_CHARS = 1200
PASSAGES_PER_DOCUMENT = 3
PARAGRAPH_BREAK = re.compile(r"\n[ \t\f\v]*\n")
SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def passage_terms(plan: RetrievalPlan) -> frozenset[str]:
    asked = [*(query.query.text for query in plan.queries), *(facet.target for facet in plan.facets)]
    named = content_stems(plan.craft.name) if plan.craft is not None else set()
    return frozenset(stem for text in asked for stem in content_stems(text)) - named


def best_passages(text: str, terms: frozenset[str], *, budget: int) -> list[str]:
    passages = passages_of(text)
    found = [content_stems(passage) & terms for passage in passages]
    weights = _rarity(found, len(passages))
    scored = sorted(
        ((sum(weights[stem] for stem in stems), index) for index, stems in enumerate(found) if stems),
        key=lambda pair: (-pair[0], pair[1]),
    )
    picked: list[str] = []
    for _, index in scored:
        if len(picked) == PASSAGES_PER_DOCUMENT:
            break
        if sum(map(len, picked)) + len(passages[index]) <= budget:
            picked.append(passages[index])
    return picked


def passages_of(text: str, *, max_chars: int = PASSAGE_MAX_CHARS) -> list[str]:
    passages: list[str] = []
    current = ""
    for unit in _units(text, max_chars):
        joined = f"{current} {unit}" if current else unit
        if current and len(joined) > max_chars:
            passages.append(current)
            current = unit
        else:
            current = joined
    if current:
        passages.append(current)
    return passages


def _rarity(found: Sequence[set[str]], count: int) -> dict[str, float]:
    spread = Counter(stem for stems in found for stem in stems)
    return {stem: math.log(1 + count / passages) for stem, passages in spread.items()}


def _units(text: str, max_chars: int) -> Iterable[str]:
    for paragraph in PARAGRAPH_BREAK.split(text):
        flat = normalise_quote_text(paragraph)
        for sentence in SENTENCE_END.split(flat) if flat else ():
            yield from _cut(sentence, max_chars)


def _cut(sentence: str, max_chars: int) -> list[str]:
    if len(sentence) <= max_chars:
        return [sentence]
    pieces: list[str] = []
    current = ""
    for word in sentence.split(" "):
        joined = f"{current} {word}" if current else word
        if current and len(joined) > max_chars:
            pieces.append(current)
            current = word
        else:
            current = joined
    if current:
        pieces.append(current)
    return pieces
