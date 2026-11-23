from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from app.models.knowledge import DIFFERS_ON_CHARS

from .candidate_gates import COMPARISON_RELATIONS, REASON_MAX_CHARS
from .quotes import quote_key

__all__ = [
    "NEW_DETAILS_MAX",
    "ComparedFacts",
    "comparison_relation",
    "differs_about",
    "novelty_adds",
    "novelty_reason",
    "relation_reason",
]

SAME, DIFFERS, DISTINCT = COMPARISON_RELATIONS
NEW_DETAILS_MAX = 12
GENERAL = "it is too general to teach a reader anything about this craft"


@dataclass(frozen=True)
class ComparedFacts:
    same: bool
    same_subject: bool
    same_property: bool
    same_when: bool
    both_true: bool
    subject: str
    property: str
    candidate_value: str
    held_value: str

    def values_clash(self) -> bool:
        said, held = _folded(self.candidate_value), _folded(self.held_value)
        return bool(said) and bool(held) and said != held


def comparison_relation(compared: ComparedFacts) -> str:
    if compared.same:
        return SAME
    one_question = compared.same_subject and compared.same_property and compared.same_when
    if one_question and not compared.both_true and compared.values_clash():
        return DIFFERS
    return DISTINCT


def relation_reason(compared: ComparedFacts, relation: str, said: str) -> str:
    if relation != DIFFERS:
        return said[:REASON_MAX_CHARS]
    clash = f"{_named(compared)}: the candidate says {compared.candidate_value}, the held fact {compared.held_value}"
    return f"{clash}. {said}"[:REASON_MAX_CHARS]


def differs_about(compared: ComparedFacts, relation: str) -> str | None:
    named = _named(compared).strip(" ,.")
    if relation != DIFFERS or not named:
        return None
    return f"{named[0].upper()}{named[1:]}"[:DIFFERS_ON_CHARS]


def _named(compared: ComparedFacts) -> str:
    subject, asked = compared.subject.strip(), compared.property.strip()
    return f"{subject}, {asked}" if subject and asked else subject or asked


def novelty_adds(new_details: Sequence[str], *, specific: bool) -> bool:
    return specific and any(detail.strip() for detail in new_details)


def novelty_reason(new_details: Sequence[str], *, specific: bool, said: str) -> str:
    details = [detail.strip() for detail in new_details if detail.strip()]
    if details and specific:
        return f"it states what the held facts do not: {'; '.join(details)}. {said}"[:REASON_MAX_CHARS]
    if not specific:
        return f"{GENERAL}. {said}"[:REASON_MAX_CHARS]
    return said[:REASON_MAX_CHARS]


def _folded(value: str) -> str:
    return quote_key(value).casefold().strip(" .")
