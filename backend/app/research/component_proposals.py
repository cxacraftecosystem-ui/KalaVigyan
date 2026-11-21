from __future__ import annotations

import re
import uuid
from collections.abc import Iterable, Sequence
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.knowledge_pieces import DESCRIPTION_MAX_CHARS, LABEL_PATTERN, TITLE_COLUMN_CHARS
from app.models.open_work import PROPOSAL_EXTENSIONS, PROPOSAL_STATUSES

from .base import ContractModel
from .component_specs import not_contributable
from .component_specs_general_delivery import UNITS_MAX, DeliveredUnit, UnitKey
from .crafts import SLUG_MAX_CHARS
from .knowledge_api import ComponentSummary
from .open_work import COMPONENT_NEEDS, TASK_KEY_MAX_CHARS, parse_task_key
from .vocabulary import Discipline, PieceKind, PieceSubjectKind

__all__ = [
    "CLOSE_TEXT_OVERLAP",
    "CLOSE_TITLE_OVERLAP",
    "COMPONENT_PROPOSAL_SCHEMA_VERSION",
    "EXTENSIONS",
    "PROPOSAL_STATUSES",
    "SUBJECT_LINK",
    "VARIANT",
    "WAYS_ON",
    "ComponentMatch",
    "ComponentProposalDraft",
    "ComponentProposalResult",
    "ProposedSubject",
    "close_matches",
    "content_words",
    "match_reasons",
    "proposal_crafts",
    "task_problem",
    "word_overlap",
]

COMPONENT_PROPOSAL_SCHEMA_VERSION = 1
EXTENSIONS = PROPOSAL_EXTENSIONS
SUBJECT_LINK, VARIANT = PROPOSAL_EXTENSIONS
COMPONENT_TASK = "MISSING_COMPONENT"
OUTCOMES = ("STORED", "REFUSED")
CLOSE_TITLE_OVERLAP = 0.5
CLOSE_TEXT_OVERLAP = 0.6
WORD_MIN_CHARS = 3
DESCRIPTION_MIN_CHARS = 40
SUBJECTS_MAX = 20
CONSIDERED_MAX = 50
SUBJECT_KEY_MAX_CHARS = 64
SHARED_KEY_KINDS = frozenset({"CONCEPT", "COMPOUND", "PLACE"})
WORD_PATTERN = re.compile(r"[a-z0-9]+")
STOP_WORDS = frozenset(
    {
        "and",
        "the",
        "for",
        "with",
        "from",
        "into",
        "its",
        "how",
        "that",
        "this",
        "what",
        "which",
        "when",
        "where",
        "are",
        "was",
        "were",
        "each",
        "one",
        "show",
        "shows",
        "component",
        "player",
        "reader",
    }
)
WAYS_ON = (
    "Place the existing component by its label: name the label in the page's layout or the answer instead "
    "of making another.",
    "Propose an extension of it: propose the component again with extends set to its label and extension "
    "SUBJECT_LINK to key it to a new craft, concept, compound or place, or VARIANT for a different form of "
    "the same thing. Never a copy.",
)

ProposalStatus = Literal[*PROPOSAL_STATUSES]
Extension = Literal[*EXTENSIONS]
Outcome = Literal[*OUTCOMES]


class ProposedSubject(ContractModel):
    kind: PieceSubjectKind
    key: str = Field(min_length=1, max_length=SUBJECT_KEY_MAX_CHARS)


class ComponentProposalDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    label: str = Field(max_length=TITLE_COLUMN_CHARS, pattern=LABEL_PATTERN)
    title: str = Field(min_length=3, max_length=TITLE_COLUMN_CHARS)
    description: str = Field(min_length=DESCRIPTION_MIN_CHARS, max_length=DESCRIPTION_MAX_CHARS)
    kind: PieceKind
    field: Discipline
    fields: list[Discipline] = Field(default_factory=list)
    craft_slug: str | None = Field(default=None, min_length=1, max_length=SLUG_MAX_CHARS)
    subjects: list[ProposedSubject] = Field(min_length=1, max_length=SUBJECTS_MAX)
    considered_labels: list[str] = Field(default_factory=list, max_length=CONSIDERED_MAX)
    extends: str | None = Field(default=None, max_length=TITLE_COLUMN_CHARS, pattern=LABEL_PATTERN)
    extension: Extension | None = None
    task_key: str | None = Field(default=None, min_length=1, max_length=TASK_KEY_MAX_CHARS)
    spec: dict[str, Any] | None = None
    units: dict[UnitKey, DeliveredUnit] = Field(default_factory=dict, max_length=UNITS_MAX)

    @property
    def delivered(self) -> bool:
        return self.spec is not None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        refused = not_contributable(self.kind)
        if refused is not None:
            raise ValueError(refused)
        if (self.extends is None) != (self.extension is None):
            raise ValueError("extends and extension come together: the label extended and how")
        if self.extension == SUBJECT_LINK and self.label != self.extends:
            raise ValueError("a SUBJECT_LINK keeps the label of the component it extends")
        if self.extension == VARIANT and self.label == self.extends:
            raise ValueError("a VARIANT is a new component with a label of its own")
        if self.field in self.fields or len(set(self.fields)) != len(self.fields):
            raise ValueError("fields lists further fields once each, never the main field")
        keys = [(subject.kind, subject.key) for subject in self.subjects]
        if len(set(keys)) != len(keys):
            raise ValueError("each subject is named once")
        if len(set(self.considered_labels)) != len(self.considered_labels):
            raise ValueError("each considered label is named once")
        if self.units and self.spec is None:
            raise ValueError("units come with the spec that places them")
        if self.extension == SUBJECT_LINK and self.spec is not None:
            raise ValueError(
                "a SUBJECT_LINK keys the registered component to new subjects and carries no spec"
            )
        return self


class ComponentMatch(ContractModel):
    component: ComponentSummary
    reasons: list[str] = Field(min_length=1)


class ComponentProposalResult(ContractModel):
    schema_version: Literal[1] = COMPONENT_PROPOSAL_SCHEMA_VERSION
    outcome: Outcome
    proposal_id: uuid.UUID | None = None
    status: ProposalStatus | None = None
    label: str
    message: str
    matches: list[ComponentMatch] = Field(default_factory=list)
    ways_on: list[str] = Field(default_factory=list)


def content_words(text: str) -> frozenset[str]:
    return frozenset(
        word
        for word in WORD_PATTERN.findall(text.casefold())
        if len(word) >= WORD_MIN_CHARS and word not in STOP_WORDS
    )


def word_overlap(first: frozenset[str], second: frozenset[str]) -> float:
    union = first | second
    return len(first & second) / len(union) if union else 0.0


def match_reasons(draft: ComponentProposalDraft, candidate: ComponentSummary) -> list[str]:
    reasons = []
    if candidate.label == draft.label:
        reasons.append("it already has this label")
    same_kind = candidate.kind == draft.kind
    shared = _shared_keys(draft.subjects, candidate)
    if same_kind and shared:
        reasons.append(f"the same kind, keyed to the same {', '.join(shared)}")
    title = word_overlap(content_words(draft.title), content_words(candidate.title))
    if same_kind and title >= CLOSE_TITLE_OVERLAP:
        reasons.append(f"the same kind with a title sharing {title:.0%} of its words")
    text = word_overlap(
        _words(draft.title, draft.description), _words(candidate.title, candidate.description)
    )
    if text >= CLOSE_TEXT_OVERLAP:
        reasons.append(f"a title and description sharing {text:.0%} of their words")
    return reasons


def close_matches(
    draft: ComponentProposalDraft, candidates: Iterable[ComponentSummary]
) -> list[ComponentMatch]:
    seen: set[str] = set()
    found = []
    for candidate in candidates:
        if candidate.label in seen or candidate.label == draft.extends:
            continue
        seen.add(candidate.label)
        reasons = match_reasons(draft, candidate)
        if reasons:
            found.append(ComponentMatch(component=candidate, reasons=reasons))
    return found


def proposal_crafts(draft: ComponentProposalDraft) -> list[str]:
    slugs = [draft.craft_slug] if draft.craft_slug else []
    slugs += [subject.key for subject in draft.subjects if subject.kind == "CRAFT"]
    return list(dict.fromkeys(slugs))


def task_problem(draft: ComponentProposalDraft) -> str | None:
    if draft.task_key is None:
        return None
    key = parse_task_key(draft.task_key)
    if key.kind != COMPONENT_TASK or key.detail not in COMPONENT_NEEDS:
        return f"{draft.task_key} is not a missing-component task; only those are completed by a proposal"
    if draft.kind not in COMPONENT_NEEDS[key.detail]:
        return f"a {key.detail} task is completed by a component of kind {', '.join(COMPONENT_NEEDS[key.detail])}"
    if key.slug not in proposal_crafts(draft):
        return f"the proposal completes {draft.task_key} only when it is keyed to the craft {key.slug}"
    return None


def _words(title: str, description: str) -> frozenset[str]:
    return content_words(f"{title} {description}")


def _shared_keys(subjects: Sequence[ProposedSubject], candidate: ComponentSummary) -> list[str]:
    proposed = {
        (subject.kind, subject.key.casefold()) for subject in subjects if subject.kind in SHARED_KEY_KINDS
    }
    return sorted(
        f"{subject.kind.lower()} {subject.name}"
        for subject in candidate.subjects
        if (subject.kind, subject.key.casefold()) in proposed
    )
