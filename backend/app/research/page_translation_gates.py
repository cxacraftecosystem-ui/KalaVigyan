from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Literal

from .base import ContractModel
from .translation import translation_problems
from .translation_passages import PassageLeaf

__all__ = [
    "ADDED",
    "CURRENT",
    "KEPT",
    "LENGTH_RATIO_MAX",
    "LENGTH_SLACK_CHARS",
    "SHAPE",
    "TRANSLATION_GATES",
    "GateInput",
    "TranslationCheck",
    "checks_passed",
    "refusal",
    "translation_checks",
]

TRANSLATION_GATES = ("CURRENT", "SHAPE", "KEPT", "ADDED")
CURRENT, SHAPE, KEPT, ADDED = TRANSLATION_GATES
LENGTH_RATIO_MAX = 3
LENGTH_SLACK_CHARS = 40
LINK = re.compile(r"https?://|www\.", re.IGNORECASE)
CHANGED = (
    "The English passage changed after it was read: read its current texts and source_hash and translate "
    "them again."
)
COUNT = "The passage holds {held} texts and the translation gives {given}: one text for each, in order."
FIXED = "texts[{at}] is a name, a botanical name, a quote or part of a formula and stays exactly {text!r}."
CITED = "texts[{at}] carries the citation and holds the sentence's last words, so it cannot be empty."
LONGER = (
    "The translation runs to {given} characters for an English passage of {held}: a translation says what "
    "the English says and adds nothing."
)
LINKED = "The translation holds a link the English passage does not."

TranslationGate = Literal[*TRANSLATION_GATES]


class TranslationCheck(ContractModel):
    check: TranslationGate
    passed: bool
    reasons: list[str]


@dataclass(frozen=True)
class GateInput:
    leaves: Sequence[PassageLeaf]
    current_hash: str
    given_hash: str
    texts: Sequence[str]
    language: str


def translation_checks(given: GateInput) -> list[TranslationCheck]:
    current = _checked(CURRENT, [] if given.given_hash == given.current_hash else [CHANGED])
    if not current.passed:
        return [current]
    shape = _checked(SHAPE, _shape_reasons(given.leaves, given.texts))
    if not shape.passed:
        return [current, shape]
    english, translated = _prose(given.leaves, given.texts)
    kept = _checked(KEPT, translation_problems(english, translated, language=given.language))
    return [current, shape, kept, _checked(ADDED, _added_reasons(english, translated))]


def checks_passed(checks: Sequence[TranslationCheck]) -> bool:
    return all(check.passed for check in checks)


def refusal(checks: Sequence[TranslationCheck]) -> TranslationCheck | None:
    return next((check for check in checks if not check.passed), None)


def _checked(gate: str, reasons: list[str]) -> TranslationCheck:
    return TranslationCheck(check=gate, passed=not reasons, reasons=reasons)


def _shape_reasons(leaves: Sequence[PassageLeaf], texts: Sequence[str]) -> list[str]:
    if len(texts) != len(leaves):
        return [COUNT.format(held=len(leaves), given=len(texts))]
    reasons: list[str] = []
    for at, (leaf, text) in enumerate(zip(leaves, texts, strict=True)):
        if leaf.fixed and text != leaf.text:
            reasons.append(FIXED.format(at=at, text=leaf.text))
        elif leaf.cited and leaf.text.strip() and not text.strip():
            reasons.append(CITED.format(at=at))
    return reasons


def _prose(leaves: Sequence[PassageLeaf], texts: Sequence[str]) -> tuple[str, str]:
    pairs = [(leaf.text, text) for leaf, text in zip(leaves, texts, strict=True) if not leaf.fixed]
    return "".join(english for english, _ in pairs), "".join(text for _, text in pairs)


def _added_reasons(english: str, translated: str) -> list[str]:
    reasons: list[str] = []
    if len(translated) > LENGTH_RATIO_MAX * len(english) + LENGTH_SLACK_CHARS:
        reasons.append(LONGER.format(given=len(translated), held=len(english)))
    if LINK.search(translated) and not LINK.search(english):
        reasons.append(LINKED)
    return reasons
