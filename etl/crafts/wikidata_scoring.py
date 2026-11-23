from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from app.data.craft_master_loader import MasterCraft
from app.data.craft_text import ascii_key

from wikidata_families import family_hints
from wikidata_names import (
    Candidate,
    candidate_names,
    distinctive,
    name_similarity,
    shares_distinctive,
    strip_disambiguation,
)
from wikidata_vocabulary import (
    GI_INDIA,
    INDIA,
    INDIAN_STATES,
    NEGATIVE,
    POSITIVE,
    STRONG_NEGATIVE_EXTRA,
    STRONG_NEGATIVE_TYPES,
)

__all__ = [
    "ACCEPT",
    "CATCH_ALL",
    "FLAG",
    "LOW_CONFIDENCE",
    "MARGIN",
    "MATCHED",
    "NO_MATCH",
    "decide",
    "is_gi",
    "score",
]

MATCHED = "MATCHED"
LOW_CONFIDENCE = "LOW_CONFIDENCE"
NO_MATCH = "NO_MATCH"
CATCH_ALL = "CATCH_ALL"

ACCEPT = 0.80
FLAG = 0.60
MARGIN = 0.05


@dataclass(frozen=True)
class _TypeVerdict:
    score: float
    reason: str
    hard_negative: bool


def score(craft: MasterCraft, names: list[str], cand: Candidate, labels: dict[str, str]) -> tuple[float, list[str]]:
    reasons: list[str] = []
    sim = name_similarity(names, candidate_names(cand))
    reasons.append(f"name {sim:.2f}")
    types, extra = _text_blob(cand, labels)
    kind = _type_verdict(types, extra)
    reasons.append(kind.reason)
    india = _india_score(cand, extra, reasons)
    located = " ".join(labels.get(q, "") for q in cand.claims.get("P131", [])).lower()
    blob = f"{extra} {located} {cand.sitelinks.get('enwiki', '').lower()}"
    state = _state_score(craft, blob, reasons)
    bonus = _gi_bonus(craft, cand, reasons)
    confidence = 0.55 * sim + 0.25 * kind.score + 0.10 * india + 0.10 * state + bonus
    confidence = _capped(confidence, sim=sim, kind=kind, india=india)
    confidence = _family_capped(confidence, craft, f"{types} {blob}", reasons)
    confidence = _distinctive_capped(confidence, names, cand, reasons)
    return round(min(confidence, 1.0), 4), reasons


def decide(ranked: list[tuple[float, Candidate, list[str]]]) -> str:
    if not ranked:
        return NO_MATCH
    top = ranked[0][0]
    second = ranked[1][0] if len(ranked) > 1 else 0.0
    if top >= ACCEPT and top - second >= MARGIN:
        return MATCHED
    if top >= FLAG:
        return LOW_CONFIDENCE
    return NO_MATCH


def is_gi(cand: Candidate) -> tuple[bool, list[str]]:
    cats = [c for c in cand.enwiki.get("categories", []) if "geographical indication" in c.lower()]
    return (GI_INDIA in cand.claims.get("P1389", []) or bool(cats)), cats


def _text_blob(cand: Candidate, labels: dict[str, str]) -> tuple[str, str]:
    types = " ".join(labels.get(q, "") for q in cand.claims.get("P31", []) + cand.claims.get("P279", []))
    title = cand.sitelinks.get("enwiki", "")
    disamb = strip_disambiguation(title)[1] or ""
    extra = " ".join(
        [
            cand.descriptions.get("en", ""),
            cand.enwiki.get("description", ""),
            " ".join(cand.enwiki.get("categories", [])),
            disamb,
        ]
    )
    return f" {types.lower()} ", f" {extra.lower()} "


def _has(blob: str, words: Iterable[str]) -> list[str]:
    found: list[str] = []
    for word in words:
        tail = r"(?:e?s)?(?![a-z])" if len(word.strip()) <= 3 else ""
        if re.search(r"(?<![a-z])" + re.escape(word) + tail, blob):
            found.append(word)
    return found


def _type_verdict(types: str, extra: str) -> _TypeVerdict:
    pos_types = _has(types, POSITIVE)
    neg_types = _has(types, NEGATIVE)
    pos_extra = _has(extra, POSITIVE)
    neg_extra = _has(extra, NEGATIVE) if not types.strip() else []
    hard_negative = bool(neg_types and not pos_types) or bool(neg_extra and not pos_extra and not pos_types)
    strong = _has(types, STRONG_NEGATIVE_TYPES) or (_has(extra, STRONG_NEGATIVE_EXTRA) if not types.strip() else [])
    if strong:
        hard_negative = True
        neg_types = [*neg_types, *strong]
        pos_types = []
        pos_extra = []
    if pos_types or (pos_extra and not neg_types):
        return _TypeVerdict(1.0, "craft type", hard_negative)
    if hard_negative:
        named = ", ".join(sorted(set(neg_types or neg_extra))[:3])
        return _TypeVerdict(0.0, "non-craft type: " + named, hard_negative)
    return _TypeVerdict(0.4, "type unknown", hard_negative)


def _india_score(cand: Candidate, extra: str, reasons: list[str]) -> float:
    countries = set(cand.claims.get("P17", []) + cand.claims.get("P495", []))
    india_text = bool(re.search(r"\bindia|indian\b", extra)) or bool(_has(extra, INDIAN_STATES))
    if INDIA in countries or india_text:
        reasons.append("India")
        return 1.0
    if countries:
        reasons.append("other country")
        return 0.0
    return 0.5


def _state_score(craft: MasterCraft, blob: str, reasons: list[str]) -> float:
    states = [s.lower() for s in (*craft.state_of_practice, *craft.state_of_origin) if s != "All India"]
    if states and any(s in blob for s in states):
        reasons.append("state")
        return 1.0
    return 0.5


def _gi_bonus(craft: MasterCraft, cand: Candidate, reasons: list[str]) -> float:
    gi, _ = is_gi(cand)
    if gi and craft.gi_status == "GI":
        reasons.append("GI agrees")
        return 0.05
    return 0.0


def _capped(confidence: float, *, sim: float, kind: _TypeVerdict, india: float) -> float:
    if kind.hard_negative:
        confidence = min(confidence, 0.45)
    if sim < 0.6:
        confidence = min(confidence, 0.55)
    if sim < 0.75:
        confidence = min(confidence, ACCEPT - 0.01)
    if kind.score < 1.0 or india == 0.0:
        confidence = min(confidence, ACCEPT - 0.01)
    return confidence


def _family_capped(confidence: float, craft: MasterCraft, text: str, reasons: list[str]) -> float:
    hints = family_hints(craft)
    if hints and not _has(text, hints):
        reasons.append("outside the craft's family")
        return min(confidence, ACCEPT - 0.01)
    return confidence


def _distinctive_capped(confidence: float, names: list[str], cand: Candidate, reasons: list[str]) -> float:
    cand_names = candidate_names(cand)
    if shares_distinctive(names[:1], cand_names) is not False:
        return confidence
    own = set().union(*(distinctive(ascii_key(n).split()) for n in cand_names)) if cand_names else set()
    if own:
        reasons.append("no shared distinctive word")
        return min(confidence, ACCEPT - 0.01)
    reasons.append("generic item")
    return min(confidence, FLAG - 0.01)
