from __future__ import annotations

import re
import uuid
from collections.abc import Iterable, Mapping
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.knowledge_pieces import DESCRIPTION_MAX_CHARS, LABEL_PATTERN, TITLE_COLUMN_CHARS
from app.models.open_work import PROPOSAL_EXTENSIONS, PROPOSAL_STATUSES

from .base import ContractModel
from .component_showing import Showing, delivered_showing, same_showing
from .component_specs import not_contributable
from .component_specs_general_delivery import UNITS_MAX, DeliveredUnit, UnitKey
from .crafts import SLUG_MAX_CHARS
from .knowledge_api import ComponentSummary
from .open_work import COMPONENT_NEEDS, TASK_KEY_MAX_CHARS, parse_task_key
from .open_work_flagships import FLAGSHIP_TASK, flagship_problem
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
    "Showings",
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
Showings = Mapping[str, Showing]
Extension = Literal[*EXTENSIONS]
Outcome = Literal[*OUTCOMES]


class ProposedSubject(ContractModel):
    kind: PieceSubjectKind
    key: str = Field(min_length=1, max_length=SUBJECT_KEY_MAX_CHARS)


KIND_DESCRIPTION = (
    "A component kind that takes a spec: one of kalavigyan://components/{kind}.schema.json, which "
    "resources/templates/list names"
)
REPLACES_DESCRIPTION = "The label of a registered component this one takes the place of on every page"
REPLACES_ITSELF = "a replacement takes a label of its own and is never a SUBJECT_LINK"


class ComponentProposalDraft(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    label: str = Field(max_length=TITLE_COLUMN_CHARS, pattern=LABEL_PATTERN)
    title: str = Field(min_length=3, max_length=TITLE_COLUMN_CHARS)
    description: str = Field(min_length=DESCRIPTION_MIN_CHARS, max_length=DESCRIPTION_MAX_CHARS)
    kind: PieceKind = Field(description=KIND_DESCRIPTION)
    field: Discipline
    fields: list[Discipline] = Field(default_factory=list)
    craft_slug: str | None = Field(default=None, min_length=1, max_length=SLUG_MAX_CHARS)
    subjects: list[ProposedSubject] = Field(min_length=1, max_length=SUBJECTS_MAX)
    considered_labels: list[str] = Field(default_factory=list, max_length=CONSIDERED_MAX)
    extends: str | None = Field(default=None, max_length=TITLE_COLUMN_CHARS, pattern=LABEL_PATTERN)
    extension: Extension | None = None
    replaces: str | None = Field(
        default=None, max_length=TITLE_COLUMN_CHARS, pattern=LABEL_PATTERN, description=REPLACES_DESCRIPTION
    )
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
        if self.replaces is not None and (self.replaces == self.label or self.extension == SUBJECT_LINK):
            raise ValueError(REPLACES_ITSELF)
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


def match_reasons(
    draft: ComponentProposalDraft, candidate: ComponentSummary, shown: Showing | None
) -> list[str]:
    return _reasons(draft, _drawn(draft), candidate, shown)


def close_matches(
    draft: ComponentProposalDraft, candidates: Iterable[ComponentSummary], showings: Showings
) -> list[ComponentMatch]:
    drawn = _drawn(draft)
    seen: set[str] = set()
    found = []
    for candidate in candidates:
        if candidate.label in seen or candidate.label in (draft.extends, draft.replaces):
            continue
        seen.add(candidate.label)
        reasons = _reasons(draft, drawn, candidate, showings.get(candidate.label))
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
    if key.kind == FLAGSHIP_TASK:
        return flagship_problem(key, draft.kind, proposal_crafts(draft), delivered=draft.delivered)
    if key.kind != COMPONENT_TASK or key.detail not in COMPONENT_NEEDS:
        return f"{draft.task_key} is not a missing-component task or a flagship task; only those are completed by a proposal"
    if draft.kind not in COMPONENT_NEEDS[key.detail]:
        return f"a {key.detail} task is completed by a component of kind {', '.join(COMPONENT_NEEDS[key.detail])}"
    if key.slug not in proposal_crafts(draft):
        return f"the proposal completes {draft.task_key} only when it is keyed to the craft {key.slug}"
    return None


def _drawn(draft: ComponentProposalDraft) -> Showing | None:
    return None if draft.spec is None else delivered_showing(draft.kind, draft.spec, draft.units)


def _reasons(
    draft: ComponentProposalDraft, drawn: Showing | None, candidate: ComponentSummary, shown: Showing | None
) -> list[str]:
    reasons = ["it already has this label"] if candidate.label == draft.label else []
    if drawn is None or shown is None:
        return [*reasons, *_word_reasons(draft, candidate)]
    same = same_showing(drawn, shown) if candidate.kind == draft.kind else None
    return [*reasons, *([] if same is None else [same])]


def _word_reasons(draft: ComponentProposalDraft, candidate: ComponentSummary) -> list[str]:
    reasons = []
    title = word_overlap(content_words(draft.title), content_words(candidate.title))
    if candidate.kind == draft.kind and title >= CLOSE_TITLE_OVERLAP:
        reasons.append(f"the same kind with a title sharing {title:.0%} of its words")
    text = word_overlap(
        _words(draft.title, draft.description), _words(candidate.title, candidate.description)
    )
    if text >= CLOSE_TEXT_OVERLAP:
        reasons.append(f"a title and description sharing {text:.0%} of their words")
    return reasons


def _words(title: str, description: str) -> frozenset[str]:
    return content_words(f"{title} {description}")
