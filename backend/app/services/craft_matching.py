from __future__ import annotations

import uuid
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass

from rapidfuzz import fuzz, process

from app.data.craft_text import core_key, script_of, to_latin_spoken
from app.research.crafts import (
    FUZZY_MIN_SIMILARITY,
    MAX_CANDIDATES,
    CraftCandidate,
    CraftResolution,
    MatchReason,
    clear_winner,
)
from app.services.craft_index import EXACT_SCORES, MIN_KEY_CHARS, CraftIndex

__all__ = [
    "AGREEMENT_BONUS",
    "FAMILY_WEIGHT",
    "FUZZY_TOP_K",
    "FUZZY_WEIGHT",
    "REGION_WEIGHT",
    "SEMANTIC_MIN_SIMILARITY",
    "SEMANTIC_TOP_K",
    "SEMANTIC_WEIGHT",
    "LexicalMatch",
    "SemanticHit",
    "lexical_match",
    "ranked_candidates",
    "resolution_from",
    "slug_resolution",
]

FUZZY_TOP_K = 10
FUZZY_WEIGHT = 0.95
FAMILY_WEIGHT = 0.7
SEMANTIC_TOP_K = 10
SEMANTIC_MIN_SIMILARITY = 0.6
SEMANTIC_WEIGHT = 0.8
AGREEMENT_BONUS = 0.05
REGION_WEIGHT = 0.2
PLACE_REASON_SCORE = 1.0
SCORE_DIGITS = 6
SIGNAL_OF: Mapping[str, str] = dict.fromkeys(EXACT_SCORES, "EXACT") | {
    "FUZZY": "PARTIAL",
    "FAMILY": "PARTIAL",
    "SEMANTIC": "SEMANTIC",
}
WEIGHTS: Mapping[str, float] = {"FUZZY": FUZZY_WEIGHT, "FAMILY": FAMILY_WEIGHT, "SEMANTIC": SEMANTIC_WEIGHT}


@dataclass(frozen=True)
class SemanticHit:
    craft_id: uuid.UUID
    similarity: float


@dataclass(frozen=True)
class LexicalMatch:
    normalised: str
    script: str
    reasons: Mapping[uuid.UUID, tuple[MatchReason, ...]]
    hints: frozenset[str]


@dataclass(frozen=True)
class Phrase:
    variant: int
    start: int
    end: int
    key: str

    def overlaps(self, other: Phrase) -> bool:
        return self.variant == other.variant and self.start < other.end and other.start < self.end

    def inside(self, other: Phrase) -> bool:
        return (
            self.variant == other.variant
            and other.start <= self.start
            and self.end <= other.end
            and other.end - other.start > self.end - self.start
        )


def slug_resolution(index: CraftIndex, slug: str, text: str) -> CraftResolution:
    target = index.slugs.get(slug)
    base = {"normalised": core_key(text), "script": script_of(text)}
    if target is None:
        return CraftResolution(status="NONE", craft=None, candidates=[], **base)
    kind = "MERGED_REDIRECT" if target.redirected else "EXACT_SLUG"
    score = EXACT_SCORES["EXACT_SLUG"]
    ref = index.refs[target.craft_id]
    top = CraftCandidate(craft=ref, score=score, reasons=[MatchReason(kind=kind, matched=slug, score=score)])
    return CraftResolution(status="RESOLVED", craft=ref, candidates=[top], **base)


def lexical_match(index: CraftIndex, text: str) -> LexicalMatch:
    phrases, exact = _best_reading(index, _phrases(text, index.max_tokens))
    free = [p for p in phrases if not any(p.overlaps(e) for e in exact)]
    placed = [p for p in free if p.key in index.places]
    named = [p for p in free if not any(p.overlaps(q) for q in placed)]
    reasons: dict[uuid.UUID, list[MatchReason]] = {}
    for craft_id, reason in _exact_reasons(index, exact):
        _add(reasons, craft_id, reason)
    for craft_id, reason in _fuzzy_reasons(index, named):
        _add(reasons, craft_id, reason)
    for craft_id, reason in _family_reasons(index, [p for p in named if p.end - p.start == 1]):
        _add(reasons, craft_id, reason)
    return LexicalMatch(
        normalised=core_key(text),
        script=script_of(text),
        reasons={k: tuple(v) for k, v in reasons.items()},
        hints=frozenset(p.key for p in placed),
    )


def resolution_from(
    index: CraftIndex, match: LexicalMatch, semantic: Sequence[SemanticHit] = ()
) -> CraftResolution:
    reasons = {k: list(v) for k, v in match.reasons.items()}
    for hit in semantic:
        if hit.craft_id in index.refs and hit.similarity >= SEMANTIC_MIN_SIMILARITY:
            name = index.refs[hit.craft_id].name
            _add(
                reasons,
                hit.craft_id,
                MatchReason(kind="SEMANTIC", matched=name, score=_round(hit.similarity)),
            )
    shown = _rank(index, reasons, match.hints)[:MAX_CANDIDATES]
    base = {"normalised": match.normalised, "script": match.script}
    if clear_winner(shown):
        return CraftResolution(status="RESOLVED", craft=shown[0].craft, candidates=shown, **base)
    if shown:
        return CraftResolution(status="AMBIGUOUS", craft=None, candidates=shown, **base)
    return CraftResolution(status="NONE", craft=None, candidates=[], **base)


def ranked_candidates(index: CraftIndex, match: LexicalMatch) -> list[CraftCandidate]:
    return _rank(index, match.reasons, match.hints)


def _phrases(text: str, max_tokens: int) -> list[Phrase]:
    variants: list[tuple[str, ...]] = []
    for key in (core_key(text), core_key(to_latin_spoken(text))):
        tokens = tuple(key.split())
        if tokens and tokens not in variants:
            variants.append(tokens)
    found = []
    for number, tokens in enumerate(variants):
        for start in range(len(tokens)):
            for end in range(start + 1, min(len(tokens), start + max_tokens) + 1):
                key = " ".join(tokens[start:end])
                if len(key) >= MIN_KEY_CHARS:
                    found.append(Phrase(number, start, end, key))
    return found


def _exact_phrases(index: CraftIndex, phrases: Sequence[Phrase]) -> list[Phrase]:
    hits = [p for p in phrases if p.key in index.entries]
    return [p for p in hits if not any(p.inside(other) for other in hits)]


def _best_reading(index: CraftIndex, phrases: Sequence[Phrase]) -> tuple[list[Phrase], list[Phrase]]:
    exact = _exact_phrases(index, phrases)
    if not exact:
        return list(phrases), []
    covered: dict[int, set[int]] = {}
    for phrase in exact:
        covered.setdefault(phrase.variant, set()).update(range(phrase.start, phrase.end))
    best = min(covered, key=lambda variant: (-len(covered[variant]), variant))
    return [p for p in phrases if p.variant == best], [p for p in exact if p.variant == best]


def _exact_reasons(index: CraftIndex, phrases: Sequence[Phrase]) -> Iterator[tuple[uuid.UUID, MatchReason]]:
    for phrase in phrases:
        for entry in index.entries[phrase.key]:
            kind = entry.reason_kind
            yield entry.craft_id, MatchReason(kind=kind, matched=entry.label, score=EXACT_SCORES[kind])


def _similar(query: str, choices: Sequence[str]) -> list[tuple[str, float]]:
    cutoff = FUZZY_MIN_SIMILARITY * 100
    found = process.extract(query, choices, scorer=fuzz.ratio, score_cutoff=cutoff, limit=FUZZY_TOP_K)
    return [(choice, _round(score / 100)) for choice, score, _ in found]


def _fuzzy_reasons(index: CraftIndex, phrases: Sequence[Phrase]) -> Iterator[tuple[uuid.UUID, MatchReason]]:
    for phrase in phrases:
        for key, score in _similar(phrase.key, index.keys):
            for entry in index.entries[key]:
                yield entry.craft_id, MatchReason(kind="FUZZY", matched=entry.label, score=score)


def _family_reasons(index: CraftIndex, phrases: Sequence[Phrase]) -> Iterator[tuple[uuid.UUID, MatchReason]]:
    choices = sorted(index.tokens)
    for phrase in phrases:
        for token, score in _similar(phrase.key, choices):
            for craft_id in sorted(index.tokens[token], key=str):
                yield craft_id, MatchReason(kind="FAMILY", matched=token, score=score)


def _add(reasons: dict[uuid.UUID, list[MatchReason]], craft_id: uuid.UUID, reason: MatchReason) -> None:
    held = reasons.setdefault(craft_id, [])
    same = next((i for i, r in enumerate(held) if r.kind == reason.kind), None)
    if same is None:
        held.append(reason)
    elif reason.score > held[same].score:
        held[same] = reason


def _contribution(reason: MatchReason) -> float:
    return reason.score * WEIGHTS.get(reason.kind, 1.0)


def _score(reasons: Sequence[MatchReason]) -> float:
    signals = {SIGNAL_OF[r.kind] for r in reasons}
    best = max(_contribution(r) for r in reasons)
    return min(1.0, best + AGREEMENT_BONUS * (len(signals) - 1))


def _rank(
    index: CraftIndex, reasons: Mapping[uuid.UUID, Sequence[MatchReason]], hints: frozenset[str]
) -> list[CraftCandidate]:
    regional = {
        c: sorted({index.places[k] for k in hints & index.craft_places.get(c, frozenset())}) for c in reasons
    }
    boosting = any(regional.values())
    candidates = []
    for craft_id, found in reasons.items():
        score = _score(found)
        listed = sorted(found, key=lambda r: (-_contribution(r), r.kind, r.matched))
        if boosting:
            places = regional[craft_id]
            score = score * (1 - REGION_WEIGHT) + (REGION_WEIGHT if places else 0.0)
            listed += [MatchReason(kind="PLACE", matched=p, score=PLACE_REASON_SCORE) for p in places]
        candidates.append(CraftCandidate(craft=index.refs[craft_id], score=_round(score), reasons=listed))
    return sorted(candidates, key=lambda c: (-c.score, c.craft.name.casefold(), c.craft.slug))


def _round(value: float) -> float:
    return round(value, SCORE_DIGITS)
