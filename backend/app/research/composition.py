from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Literal, Protocol, Self, runtime_checkable

from pydantic import Field, field_validator, model_validator

from app.core.errors import InvalidInput
from app.models.knowledge import QUOTE_MAX_CHARS
from app.models.knowledge_pieces import DESCRIPTION_MAX_CHARS, LABEL_COLUMN_CHARS

from .base import ContractModel
from .crafts import QUESTION_MAX_CHARS, CraftRef
from .evidence import EVIDENCE_ID_MAX_CHARS, SEARCH_QUERY_MAX_CHARS
from .quotes import (
    QUOTE_MIN_CHARS,
    QUOTE_OVERLAP_MIN,
    quote_occurs,
    quote_overlap,
    trivial_quote,
    unsupported_figures,
)
from .reading_style import ReadingStyle
from .sentence_support import SCREEN_KINDS, STANCE_KINDS, SupportGap, screen_gaps, stance_gaps, unrelated_refs
from .vocabulary import (
    CANONICAL_LANGUAGE,
    AnswerLanguage,
    AnswerMode,
    Discipline,
    EvidenceLevel,
    LiveTier,
    PieceKind,
    weakest_level,
)

__all__ = [
    "CANDIDATE_KINDS",
    "COMPONENTS_OFFERED_MAX",
    "COMPOSE_RETRIES",
    "FOLLOW_UPS_MAX",
    "HEADING_MAX_CHARS",
    "LEDE_SENTENCES_MAX",
    "LEDE_SENTENCES_MIN",
    "SECTION_SENTENCES_DEFAULT",
    "SECTION_SENTENCES_LIMIT",
    "SENTENCE_MAX_CHARS",
    "VIOLATION_KINDS",
    "ComponentOption",
    "ComposeCandidate",
    "ComposeFocus",
    "ComposeRequest",
    "ComposedAnswer",
    "ComposedLede",
    "ComposedSection",
    "ComposedSentence",
    "Composer",
    "LedeRequest",
    "LedeSection",
    "QuotedSpan",
    "ResearchSummary",
    "SearchedQuery",
    "SentenceViolation",
    "StageOption",
    "not_enough_evidence_message",
    "searched_note",
    "sentence_level",
    "sentence_violations",
]

COMPOSE_RETRIES = 1
SENTENCE_MAX_CHARS = 600
HEADING_MAX_CHARS = 120
FOLLOW_UPS_MAX = 5
SECTION_SENTENCES_DEFAULT = 8
SECTION_SENTENCES_LIMIT = 24
LEDE_SENTENCES_MIN = 2
LEDE_SENTENCES_MAX = 3
COMPONENTS_OFFERED_MAX = 6
CANDIDATE_KINDS = ("CLAIM", "EVIDENCE")
VIOLATION_KINDS = (
    "UNCITED",
    "UNKNOWN_ID",
    "UNQUOTED",
    "UNSUPPORTED_FIGURE",
    "SPAN_NOT_CITED",
    "SPAN_NOT_IN_SOURCE",
    "TRIVIAL_QUOTE",
    "UNRELATED_QUOTE",
    "UNRELATED_SPAN",
    *STANCE_KINDS,
    *SCREEN_KINDS,
)

CandidateKind = Literal[*CANDIDATE_KINDS]
ViolationKind = Literal[*VIOLATION_KINDS]


class ComposeCandidate(ContractModel):
    id: str = Field(min_length=3, max_length=EVIDENCE_ID_MAX_CHARS)
    kind: CandidateKind
    text: str = Field(min_length=1)
    quotes: list[str] = Field(default_factory=list)
    source_label: str = Field(min_length=1, max_length=300)
    level: EvidenceLevel

    @model_validator(mode="after")
    def _id_fits_the_kind(self) -> Self:
        if self.kind == "CLAIM":
            uuid.UUID(self.id)
        elif ":" not in self.id:
            raise ValueError("an EVIDENCE candidate has an '<adapter>:<id>' id")
        return self

    @property
    def cited_texts(self) -> list[str]:
        return [self.text, *self.quotes]


class SearchedQuery(ContractModel):
    tier: LiveTier
    text: str = Field(min_length=2, max_length=SEARCH_QUERY_MAX_CHARS)


class ResearchSummary(ContractModel):
    craft: CraftRef | None
    mode: AnswerMode
    stored_claims: int = Field(ge=0)
    stored_passages: int = Field(ge=0)
    queries: tuple[SearchedQuery, ...] = ()
    services: tuple[str, ...] = ()
    evidence_found: int = Field(ge=0)
    documents_read: int = Field(ge=0)
    failures: int = Field(ge=0)


class StageOption(ContractModel):
    id: uuid.UUID
    ordinal: int = Field(ge=0)
    name: str = Field(min_length=1, max_length=300)


class ComponentOption(ContractModel):
    label: str = Field(min_length=1, max_length=LABEL_COLUMN_CHARS)
    kind: PieceKind
    description: str = Field(min_length=1, max_length=DESCRIPTION_MAX_CHARS)


class ComposeFocus(ContractModel):
    discipline: Discipline
    title: str = Field(min_length=1, max_length=HEADING_MAX_CHARS)
    stages: list[StageOption] = Field(default_factory=list)
    sentences_max: int = Field(default=SECTION_SENTENCES_DEFAULT, ge=1, le=SECTION_SENTENCES_LIMIT)
    components: list[ComponentOption] = Field(default_factory=list, max_length=COMPONENTS_OFFERED_MAX)

    @model_validator(mode="after")
    def _each_offered_once(self) -> Self:
        if len(set(self.stage_ids)) != len(self.stages):
            raise ValueError("each process stage is offered once")
        if len(set(self.component_labels)) != len(self.components):
            raise ValueError("each component is offered once")
        return self

    @property
    def stage_ids(self) -> list[str]:
        return [str(stage.id) for stage in self.stages]

    @property
    def component_labels(self) -> list[str]:
        return [component.label for component in self.components]


class ComposeRequest(ContractModel):
    question: str = Field(min_length=2, max_length=QUESTION_MAX_CHARS)
    language: AnswerLanguage = CANONICAL_LANGUAGE
    craft: CraftRef | None
    candidates: list[ComposeCandidate] = Field(default_factory=list)
    searched: ResearchSummary
    focus: ComposeFocus | None = None
    style: ReadingStyle | None = None

    @field_validator("language")
    @classmethod
    def _composes_canonical_text(cls, language: str) -> str:
        if language != CANONICAL_LANGUAGE:
            raise ValueError(
                f"the composer writes and checks {CANONICAL_LANGUAGE} sentences; translate them afterwards "
                "with services.answer_translation"
            )
        return language

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        ids = [c.id for c in self.candidates]
        if len(ids) != len(set(ids)):
            raise ValueError("candidate ids are unique")
        if self.searched.craft != self.craft:
            raise ValueError("the research summary belongs to the request's craft")
        return self

    @property
    def allowed(self) -> dict[str, ComposeCandidate]:
        return {c.id: c for c in self.candidates}


class QuotedSpan(ContractModel):
    ref: str = Field(min_length=3, max_length=EVIDENCE_ID_MAX_CHARS)
    text: str = Field(min_length=QUOTE_MIN_CHARS, max_length=QUOTE_MAX_CHARS)


class ComposedSentence(ContractModel):
    text: str = Field(min_length=1, max_length=SENTENCE_MAX_CHARS)
    claim_ids: list[uuid.UUID] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    spans: list[QuotedSpan] = Field(default_factory=list)

    @property
    def cited_ids(self) -> list[str]:
        return [str(c) for c in self.claim_ids] + list(self.evidence_ids)


class ComposedSection(ContractModel):
    heading: str = Field(min_length=1, max_length=HEADING_MAX_CHARS)
    sentences: list[ComposedSentence] = Field(min_length=1)


class ComposedAnswer(ContractModel):
    sections: list[ComposedSection] = Field(default_factory=list)
    open_questions: list[ComposedSentence] = Field(default_factory=list)
    stage_ids: list[uuid.UUID] = Field(default_factory=list)
    follow_ups: list[str] = Field(default_factory=list, max_length=FOLLOW_UPS_MAX)
    not_enough_evidence: ResearchSummary | None = None
    heading: str | None = Field(default=None, min_length=1, max_length=HEADING_MAX_CHARS)
    component_labels: list[str] = Field(default_factory=list, max_length=COMPONENTS_OFFERED_MAX)

    @model_validator(mode="after")
    def _answers_or_says_why_not(self) -> Self:
        answered = bool(self.sections or self.open_questions or self.stage_ids)
        if answered == (self.not_enough_evidence is not None):
            raise ValueError("an answer shows something cited or a not-enough-evidence summary, never both")
        if len(set(self.stage_ids)) != len(self.stage_ids):
            raise ValueError("an answer chooses each process stage once")
        if len(set(self.component_labels)) != len(self.component_labels):
            raise ValueError("an answer places each component once")
        if self.component_labels and not answered:
            raise ValueError("an answer places components only beside what it shows")
        return self


class LedeSection(ContractModel):
    section_id: str = Field(min_length=1)
    discipline: Discipline
    claim_ids: list[str] = Field(min_length=1)


class LedeRequest(ContractModel):
    question: str = Field(min_length=2, max_length=QUESTION_MAX_CHARS)
    craft: CraftRef | None
    candidates: list[ComposeCandidate] = Field(default_factory=list)
    sections: list[LedeSection] = Field(default_factory=list)
    style: ReadingStyle | None = None

    @model_validator(mode="after")
    def _stored_claims_once_each(self) -> Self:
        ids = [c.id for c in self.candidates]
        if len(ids) != len(set(ids)) or any(c.kind != "CLAIM" for c in self.candidates):
            raise ValueError("the lede composes from stored claims, each offered once")
        if len({section.section_id for section in self.sections}) != len(self.sections):
            raise ValueError("each section is offered once for its heading")
        if any(claim not in ids for section in self.sections for claim in section.claim_ids):
            raise ValueError("a section to title shows only claims offered as candidates")
        return self

    @property
    def allowed(self) -> dict[str, ComposeCandidate]:
        return {c.id: c for c in self.candidates}


class ComposedLede(ContractModel):
    sentences: list[ComposedSentence] = Field(default_factory=list, max_length=LEDE_SENTENCES_MAX)
    headings: dict[str, str] = Field(default_factory=dict)
    follow_ups: list[str] = Field(default_factory=list, max_length=FOLLOW_UPS_MAX)


class SentenceViolation(ContractModel):
    kind: ViolationKind
    detail: str


def sentence_violations(
    sentence: ComposedSentence, allowed: Mapping[str, ComposeCandidate]
) -> list[SentenceViolation]:
    cited = sentence.cited_ids
    if not cited:
        return [SentenceViolation(kind="UNCITED", detail="the sentence cites nothing")]
    found = [SentenceViolation(kind="UNKNOWN_ID", detail=i) for i in cited if i not in allowed]
    if not sentence.spans:
        found.append(SentenceViolation(kind="UNQUOTED", detail="the sentence quotes no source"))
    verified, span_problems = _checked_spans(sentence, cited, allowed)
    found += _support_violations(sentence.text, verified)
    found += _violations(screen_gaps(sentence.text))
    return found + span_problems


def _checked_spans(
    sentence: ComposedSentence, cited: list[str], allowed: Mapping[str, ComposeCandidate]
) -> tuple[dict[str, list[str]], list[SentenceViolation]]:
    verified: dict[str, list[str]] = {}
    problems: list[SentenceViolation] = []
    for span in sentence.spans:
        problem = _span_problem(span, cited, allowed)
        if problem is not None:
            problems.append(SentenceViolation(kind=problem, detail=span.ref))
        elif span.ref in allowed:
            verified.setdefault(span.ref, []).append(span.text)
    return verified, problems


def _support_violations(text: str, verified: Mapping[str, list[str]]) -> list[SentenceViolation]:
    quotes = [quote for spans in verified.values() for quote in spans]
    found = [
        SentenceViolation(kind="UNSUPPORTED_FIGURE", detail=f) for f in unsupported_figures(text, quotes)
    ]
    if not quotes:
        return found
    if quote_overlap(text, quotes) < QUOTE_OVERLAP_MIN:
        found.append(SentenceViolation(kind="UNRELATED_QUOTE", detail="the quotes do not carry its wording"))
    else:
        found += [
            SentenceViolation(kind="UNRELATED_SPAN", detail=ref) for ref in unrelated_refs(text, verified)
        ]
    return found + _violations(stance_gaps(text, quotes))


def _violations(gaps: list[SupportGap]) -> list[SentenceViolation]:
    return [SentenceViolation.model_validate({"kind": kind, "detail": detail}) for kind, detail in gaps]


def _span_problem(
    span: QuotedSpan, cited: list[str], allowed: Mapping[str, ComposeCandidate]
) -> ViolationKind | None:
    if span.ref not in cited:
        return "SPAN_NOT_CITED"
    if span.ref not in allowed:
        return None
    if trivial_quote(span.text):
        return "TRIVIAL_QUOTE"
    if not any(quote_occurs(span.text, t) for t in allowed[span.ref].cited_texts):
        return "SPAN_NOT_IN_SOURCE"
    return None


def sentence_level(sentence: ComposedSentence, allowed: Mapping[str, ComposeCandidate]) -> str:
    unknown = [i for i in sentence.cited_ids if i not in allowed]
    if unknown:
        raise InvalidInput(f"The sentence cites ids outside the allowed set: {', '.join(unknown)}")
    return weakest_level(allowed[i].level for i in sentence.cited_ids)


def not_enough_evidence_message(summary: ResearchSummary) -> str:
    about = f" about {summary.craft.name}" if summary.craft else ""
    return " ".join([f"There is not enough cited evidence to answer this{about} yet.", *_searched(summary)])


def searched_note(summary: ResearchSummary) -> str:
    return " ".join(_searched(summary))


def _searched(summary: ResearchSummary) -> list[str]:
    parts = [
        f"Searched {_count(summary.stored_claims, 'stored claim')} and "
        f"{_count(summary.stored_passages, 'stored source passage')}.",
    ]
    if summary.queries:
        listed = "; ".join(f'{query.tier} "{query.text}"' for query in summary.queries)
        parts.append(f"Live research ran {_count(len(summary.queries), 'query', 'queries')}: {listed}.")
    else:
        parts.append("No live research ran.")
    if summary.services:
        parts.append(f"Sources searched: {', '.join(summary.services)}.")
    parts.append(
        f"Found {_count(summary.evidence_found, 'item')}, read {_count(summary.documents_read, 'document')}"
        f" and recorded {_count(summary.failures, 'failed request')}."
    )
    return parts


def _count(n: int, singular: str, plural: str | None = None) -> str:
    return f"{n} {singular if n == 1 else plural or singular + 's'}"


@runtime_checkable
class Composer(Protocol):
    async def compose(self, request: ComposeRequest) -> ComposedAnswer: ...
