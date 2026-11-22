from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from types import MappingProxyType
from typing import Literal, Self

from pydantic import Field, field_validator, model_validator

from app.models.knowledge import QUOTE_MAX_CHARS

from .base import ContractModel, HttpsUrl, absent
from .candidate_gates import Gate, GateOutcome
from .evidence import canonical_url, personal_data_in
from .open_work import TASK_KEY_MAX_CHARS, parse_task_key
from .open_work_gap_keys import GAP_TASK, is_gap_detail
from .review_switch import ProposalOutcome
from .vocabulary import Discipline, EvidenceLevel

__all__ = [
    "FACT_TASK_KINDS",
    "KNOWLEDGE_WRITES_SCHEMA_VERSION",
    "PROPOSAL_FIELDS_MAX",
    "PROPOSAL_QUOTES_MAX",
    "PROPOSAL_SOURCES_MAX",
    "PROPOSAL_SUBJECT_KINDS",
    "STATEMENT_MAX_CHARS",
    "FactProposal",
    "GateReport",
    "ProposalReply",
    "ProposalSubject",
    "ProposedQuote",
    "ProposedSource",
    "ReaderPlace",
    "fact_task_problem",
    "gap_fields_problem",
    "gate_reports",
]

KNOWLEDGE_WRITES_SCHEMA_VERSION = 1
PROPOSAL_SUBJECT_KINDS = ("craft", "category")
PROPOSAL_SOURCES_MAX = 5
PROPOSAL_QUOTES_MAX = 6
PROPOSAL_FIELDS_MAX = 3
STATEMENT_MIN_CHARS = 20
STATEMENT_MAX_CHARS = 1000
SUBJECT_SLUG_MAX_CHARS = 200
TITLE_MAX_CHARS = 1000
LICENCE_MAX_CHARS = 200
LOCATOR_MAX_CHARS = 300
FACT_TASK_KINDS = ("MISSING_FIELD", "THIN_FIELD", "SECOND_SOURCE", "SOURCES_DIFFER", GAP_TASK)
FIELDLESS_TASK_KINDS = frozenset({"SECOND_SOURCE", "SOURCES_DIFFER"})
TASK_SUBJECTS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {"craft": ("craft", "family"), "category": ("category",)}
)

SubjectKind = Literal[*PROPOSAL_SUBJECT_KINDS]


class ProposalSubject(ContractModel):
    kind: SubjectKind
    slug: str = Field(min_length=1, max_length=SUBJECT_SLUG_MAX_CHARS, pattern=r"^[A-Za-z0-9-]+$")


class ProposedQuote(ContractModel):
    text: str = Field(min_length=1, max_length=QUOTE_MAX_CHARS)
    locator: str | None = Field(default=None, min_length=1, max_length=LOCATOR_MAX_CHARS)


class ProposedSource(ContractModel):
    url: HttpsUrl
    title: str = Field(min_length=1, max_length=TITLE_MAX_CHARS)
    licence: str | None = Field(default=None, min_length=1, max_length=LICENCE_MAX_CHARS)
    quotes: list[ProposedQuote] = Field(min_length=1, max_length=PROPOSAL_QUOTES_MAX)

    @model_validator(mode="after")
    def _each_quote_once(self) -> Self:
        texts = [quote.text for quote in self.quotes]
        if len(set(texts)) != len(texts):
            raise ValueError("a source gives each quote once")
        return self


class FactProposal(ContractModel):
    schema_version: Literal[1] = KNOWLEDGE_WRITES_SCHEMA_VERSION
    subject: ProposalSubject
    field: Discipline
    fields: list[Discipline] = Field(default_factory=list, max_length=PROPOSAL_FIELDS_MAX)
    statement: str = Field(min_length=STATEMENT_MIN_CHARS, max_length=STATEMENT_MAX_CHARS)
    sources: list[ProposedSource] = Field(min_length=1, max_length=PROPOSAL_SOURCES_MAX)
    task_key: str | None = Field(default=None, min_length=1, max_length=TASK_KEY_MAX_CHARS)

    @field_validator("statement")
    @classmethod
    def _no_personal_data(cls, value: str) -> str:
        found = personal_data_in(value)
        if found:
            raise ValueError(f"a fact never carries personal data ({', '.join(found)})")
        return value

    @model_validator(mode="after")
    def _fields_and_sources_are_distinct(self) -> Self:
        if self.field in self.fields or len(set(self.fields)) != len(self.fields):
            raise ValueError("secondary fields are distinct and leave out the primary field")
        urls = [canonical_url(source.url) for source in self.sources]
        if len(set(urls)) != len(urls):
            raise ValueError("each source is named once; give all its quotes under it")
        return self

    @model_validator(mode="after")
    def _task_is_this_fact_s(self) -> Self:
        if self.task_key is not None:
            problem = fact_task_problem(self.task_key, self.subject, (self.field, *self.fields))
            if problem is not None:
                raise ValueError(problem)
        return self


class GateReport(ContractModel):
    gate: Gate
    passed: bool
    reasons: list[str]


class ReaderPlace(ContractModel):
    shown: bool
    reason: str | None = None
    page_url: str | None = None
    chapter: str | None = None
    field: Discipline | None = None
    in_prose: bool = False
    write_task: str | None = Field(default=None, max_length=TASK_KEY_MAX_CHARS)

    @model_validator(mode="after")
    def _a_reason_exactly_when_hidden(self) -> Self:
        if self.shown == (self.reason is not None):
            raise ValueError("a fact readers cannot see says why, and only such a fact")
        if self.write_task is not None and (self.in_prose or not self.shown):
            raise ValueError("a write-section task is named only for a shown fact no section cites")
        return self


class ProposalReply(ContractModel):
    schema_version: Literal[1] = KNOWLEDGE_WRITES_SCHEMA_VERSION
    outcome: ProposalOutcome
    claim_id: uuid.UUID
    status: str
    level: EvidenceLevel
    approved_at_once: bool
    in_review_queue: bool
    sources_differ: bool
    differs_from: list[uuid.UUID]
    gates: list[GateReport]
    message: str
    readers: ReaderPlace | None = Field(default=None, exclude_if=absent)


def fact_task_problem(key: str, subject: ProposalSubject, fields: tuple[str, ...]) -> str | None:
    task = parse_task_key(key)
    if task.kind not in FACT_TASK_KINDS:
        return f"{key} is not a task a fact completes; a fact completes a {', '.join(FACT_TASK_KINDS)} task"
    if task.subject_kind not in TASK_SUBJECTS[subject.kind] or task.slug != subject.slug:
        return f"{key} is a task of another page than {subject.kind} {subject.slug}"
    if task.kind == GAP_TASK:
        return None if task.detail is not None and is_gap_detail(task.detail) else f"{key} names no question"
    if task.detail is None:
        return None if task.kind in FIELDLESS_TASK_KINDS else f"{key} names no field"
    if task.detail not in fields:
        return f"{key} asks for {task.detail}; the fact is filed under {', '.join(fields)}"
    return None


def gap_fields_problem(key: str, asked: Sequence[str] | None, fields: Sequence[str]) -> str | None:
    if asked is None:
        return f"{key} names no question readers asked of this page; list_open_work gives the open questions"
    if not set(asked) & set(fields):
        return f"{key} asks about {', '.join(asked)}; the fact is filed under {', '.join(fields)}"
    return None


def gate_reports(outcomes: list[GateOutcome]) -> list[GateReport]:
    return [GateReport(gate=item.gate, passed=item.passed, reasons=list(item.reasons)) for item in outcomes]
