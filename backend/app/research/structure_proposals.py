from __future__ import annotations

import uuid
from typing import Annotated, Literal, Self

from pydantic import Field, TypeAdapter, field_validator, model_validator

from .base import ContractModel, PartialDate
from .blocks import AFTER_COLOURS_MAX, AFTER_TEXT_MAX_CHARS
from .colours import ColourWord
from .crafts import SLUG_MAX_CHARS
from .evidence import canonical_url, personal_data_in
from .knowledge_writes import (
    PROPOSAL_SOURCES_MAX,
    STATEMENT_MAX_CHARS,
    ProposalSubject,
    ProposedSource,
    fact_task_problem,
)
from .named_groups import NAMED_GROUP_KINDS
from .open_work import TASK_KEY_MAX_CHARS
from .review_switch import AGENT, CONTRIBUTION
from .vocabulary import Discipline, ReactionKind

__all__ = [
    "ALTERNATIVE",
    "APPROVED_STATUS",
    "BOTANICAL_NAME",
    "CATEGORY_KINDS",
    "CATEGORY_SUBJECT",
    "CHECK_KINDS",
    "CONFLICT",
    "CONFLICT_CLAIMS_MAX",
    "GI_RECORD",
    "GLOSSARY_TERM",
    "GROUP_NAME",
    "NATIVE_NAME",
    "OPEN_QUESTION",
    "PENDING_STATUS",
    "REACTION",
    "REFUSED",
    "REFUSED_STATUS",
    "REJECTED_STATUS",
    "STAGE_AFTER",
    "STAGE_WHY",
    "STORED",
    "STRUCTURE_KINDS",
    "STRUCTURE_ORIGINS",
    "STRUCTURE_OUTCOMES",
    "STRUCTURE_SCHEMA_VERSION",
    "STRUCTURE_STATUSES",
    "WRITTEN",
    "AlternativeItem",
    "BotanicalNameItem",
    "ConflictItem",
    "GiRecordItem",
    "GlossaryTermItem",
    "GroupNameItem",
    "NativeNameItem",
    "OpenQuestionItem",
    "ReactionItem",
    "SpeciesItem",
    "StageAfterItem",
    "StageWhyItem",
    "StructureCheck",
    "StructureItem",
    "StructureKind",
    "StructureProposal",
    "StructureProposalResult",
    "StructureSource",
    "StructureSubject",
    "parsed_item",
]

STRUCTURE_SCHEMA_VERSION = 1
STRUCTURE_KINDS = (
    "STAGE_AFTER",
    "STAGE_WHY",
    "NATIVE_NAME",
    "REACTION",
    "BOTANICAL_NAME",
    "GLOSSARY_TERM",
    "CONFLICT",
    "OPEN_QUESTION",
    "GI_RECORD",
    "ALTERNATIVE",
    "GROUP_NAME",
)
(
    STAGE_AFTER,
    STAGE_WHY,
    NATIVE_NAME,
    REACTION,
    BOTANICAL_NAME,
    GLOSSARY_TERM,
    CONFLICT,
    OPEN_QUESTION,
    GI_RECORD,
    ALTERNATIVE,
    GROUP_NAME,
) = STRUCTURE_KINDS
CRAFT_SUBJECT, CATEGORY_SUBJECT = "craft", "category"
CATEGORY_KINDS = (REACTION, GLOSSARY_TERM, CONFLICT, OPEN_QUESTION)
CATEGORY_HOLDS = (
    "a category page keeps no stages, materials, native names or GI record of its own: it takes a reaction "
    "without a stage, a glossary term, an open question or a conflict"
)
STRUCTURE_ORIGINS = (CONTRIBUTION, AGENT)
STRUCTURE_STATUSES = ("PENDING", "APPROVED", "REJECTED", "REFUSED")
PENDING_STATUS, APPROVED_STATUS, REJECTED_STATUS, REFUSED_STATUS = STRUCTURE_STATUSES
STORED, WRITTEN, REFUSED = "STORED", "WRITTEN", "REFUSED"
STRUCTURE_OUTCOMES = (STORED, WRITTEN, REFUSED)
CHECK_KINDS = ("STATED", "QUOTES", "SOURCE")
CONFLICT_CLAIMS_MIN = 2
CONFLICT_CLAIMS_MAX = 6
SPECIES_MAX = 8
PROPRIETORS_MAX = 20
NAME_MAX_CHARS = 300
MEANING_MAX_CHARS = 600
QUESTION_MAX_CHARS = 600
NOTE_MAX_CHARS = 500
LANGUAGE_MAX_CHARS = 35
STATEMENT_MIN_CHARS = 20
CONFLICT_EVIDENCE = "a conflict names the held facts that disagree; it gives no new fact or task"
GROUP_NAME_EVIDENCE = (
    "a group name gives the sources whose quotes state it, and no field, statement or task: it only keeps "
    "the name out of AI pictures and is never shown as a fact"
)
ENTRY_KEY_PATTERN = r"^[A-Z]\d{2,4}$"
SCRIPT_CHARS = 4

StructureKind = Literal[*STRUCTURE_KINDS]
EntryKey = Annotated[str, Field(pattern=ENTRY_KEY_PATTERN, max_length=8)]
Name = Annotated[str, Field(min_length=1, max_length=NAME_MAX_CHARS)]
Language = Annotated[str, Field(min_length=2, max_length=LANGUAGE_MAX_CHARS)]
Script = Annotated[str, Field(min_length=SCRIPT_CHARS, max_length=SCRIPT_CHARS)]


class StructureSubject(ContractModel):
    kind: Literal["craft", "category"] = "craft"
    slug: str = Field(min_length=1, max_length=SLUG_MAX_CHARS, pattern=r"^[A-Za-z0-9-]+$")


class StageAfterItem(ContractModel):
    kind: Literal["STAGE_AFTER"] = STAGE_AFTER
    stage_key: EntryKey
    text: str = Field(min_length=1, max_length=AFTER_TEXT_MAX_CHARS)
    colours: list[ColourWord] = Field(default_factory=list, max_length=AFTER_COLOURS_MAX)

    @field_validator("colours")
    @classmethod
    def _each_colour_once(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("each colour is named once")
        return value


class StageWhyItem(ContractModel):
    kind: Literal["STAGE_WHY"] = STAGE_WHY
    stage_key: EntryKey


class NativeNameItem(ContractModel):
    kind: Literal["NATIVE_NAME"] = NATIVE_NAME
    text: Name
    language: Language
    script: Script | None = None


class SpeciesItem(ContractModel):
    name: Name
    formula: str | None = Field(default=None, min_length=1, max_length=100)


class ReactionItem(ContractModel):
    kind: Literal["REACTION"] = REACTION
    reaction_kind: ReactionKind
    stage_key: EntryKey | None = None
    reactants: list[SpeciesItem] = Field(min_length=1, max_length=SPECIES_MAX)
    products: list[SpeciesItem] = Field(min_length=1, max_length=SPECIES_MAX)


class BotanicalNameItem(ContractModel):
    kind: Literal["BOTANICAL_NAME"] = BOTANICAL_NAME
    material_key: EntryKey
    botanical_name: str = Field(min_length=1, max_length=200)


class GlossaryTermItem(ContractModel):
    kind: Literal["GLOSSARY_TERM"] = GLOSSARY_TERM
    term: Name
    meaning: str = Field(min_length=1, max_length=MEANING_MAX_CHARS)
    language: Language | None = None
    script: Script | None = None


class ConflictItem(ContractModel):
    kind: Literal["CONFLICT"] = CONFLICT
    about: Name
    claim_ids: list[uuid.UUID] = Field(min_length=CONFLICT_CLAIMS_MIN, max_length=CONFLICT_CLAIMS_MAX)

    @field_validator("claim_ids")
    @classmethod
    def _each_claim_once(cls, value: list[uuid.UUID]) -> list[uuid.UUID]:
        if len(set(value)) != len(value):
            raise ValueError("a conflict names each fact once")
        return value


class OpenQuestionItem(ContractModel):
    kind: Literal["OPEN_QUESTION"] = OPEN_QUESTION
    question: str = Field(min_length=1, max_length=QUESTION_MAX_CHARS)
    settled_by: str | None = Field(default=None, min_length=1, max_length=QUESTION_MAX_CHARS)


class GiRecordItem(ContractModel):
    kind: Literal["GI_RECORD"] = GI_RECORD
    application_number: str | None = Field(default=None, min_length=1, max_length=40)
    certificate_number: str | None = Field(default=None, min_length=1, max_length=40)
    filed_on: PartialDate | None = None
    registered_on: PartialDate | None = None
    journal_issue: str | None = Field(default=None, min_length=1, max_length=100)
    proprietors: list[Name] = Field(default_factory=list, max_length=PROPRIETORS_MAX)
    authorised_user_count: int | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def _states_something(self) -> Self:
        given = [value for name, value in self if name != "kind" and value not in (None, [])]
        if not given:
            raise ValueError("a GI record proposal states at least one part of the record")
        if len(set(self.proprietors)) != len(self.proprietors):
            raise ValueError("each proprietor is named once")
        return self


class GroupNameItem(ContractModel):
    kind: Literal["GROUP_NAME"] = GROUP_NAME
    name: Name
    group_kind: Literal[*NAMED_GROUP_KINDS]


class AlternativeItem(ContractModel):
    kind: Literal["ALTERNATIVE"] = ALTERNATIVE
    material_key: EntryKey
    alternative_key: EntryKey

    @model_validator(mode="after")
    def _two_materials(self) -> Self:
        if self.material_key == self.alternative_key:
            raise ValueError("an alternative is another material of the page than the one it stands in for")
        return self


StructureItem = Annotated[
    StageAfterItem
    | StageWhyItem
    | NativeNameItem
    | ReactionItem
    | BotanicalNameItem
    | GlossaryTermItem
    | ConflictItem
    | OpenQuestionItem
    | GiRecordItem
    | AlternativeItem
    | GroupNameItem,
    Field(discriminator="kind"),
]


ITEMS: TypeAdapter[StructureItem] = TypeAdapter(StructureItem)


def parsed_item(stored: object) -> StructureItem:
    return ITEMS.validate_python(stored)


class StructureSource(ProposedSource):
    language: Language

    @model_validator(mode="after")
    def _every_quote_has_a_locator(self) -> Self:
        if any(quote.locator is None for quote in self.quotes):
            raise ValueError("every quote of a structure proposal names where it is (its locator)")
        return self


class StructureProposal(ContractModel):
    schema_version: Literal[1] = STRUCTURE_SCHEMA_VERSION
    subject: StructureSubject
    item: StructureItem
    field: Discipline | None = None
    statement: str | None = Field(
        default=None, min_length=STATEMENT_MIN_CHARS, max_length=STATEMENT_MAX_CHARS
    )
    sources: list[StructureSource] = Field(default_factory=list, max_length=PROPOSAL_SOURCES_MAX)
    task_key: str | None = Field(default=None, min_length=1, max_length=TASK_KEY_MAX_CHARS)
    note: str | None = Field(default=None, min_length=1, max_length=NOTE_MAX_CHARS)

    @field_validator("statement")
    @classmethod
    def _no_personal_data(cls, value: str | None) -> str | None:
        found = personal_data_in(value) if value is not None else []
        if found:
            raise ValueError(f"a fact never carries personal data ({', '.join(found)})")
        return value

    @model_validator(mode="after")
    def _evidence_fits_the_kind(self) -> Self:
        problem = _evidence_problem(self)
        if problem is not None:
            raise ValueError(problem)
        return self

    @model_validator(mode="after")
    def _fits_its_page(self) -> Self:
        if self.subject.kind != CATEGORY_SUBJECT:
            return self
        staged = isinstance(self.item, ReactionItem) and self.item.stage_key is not None
        if self.item.kind not in CATEGORY_KINDS or staged:
            raise ValueError(CATEGORY_HOLDS)
        return self

    @model_validator(mode="after")
    def _task_is_this_fact_s(self) -> Self:
        if self.task_key is not None and self.field is not None:
            subject = ProposalSubject(kind=self.subject.kind, slug=self.subject.slug)
            problem = fact_task_problem(self.task_key, subject, (self.field,))
            if problem is not None:
                raise ValueError(problem)
        return self


def _evidence_problem(proposal: StructureProposal) -> str | None:
    kind, gives_fact = proposal.item.kind, proposal.statement is not None or proposal.field is not None
    if kind == CONFLICT:
        given = gives_fact or bool(proposal.sources) or proposal.task_key is not None
        return CONFLICT_EVIDENCE if given else None
    if kind == GROUP_NAME:
        if gives_fact or proposal.task_key is not None or not proposal.sources:
            return GROUP_NAME_EVIDENCE
    elif proposal.statement is None or proposal.field is None or not proposal.sources:
        return f"a {kind} proposal gives the fact that states it: field, statement, sources"
    urls = [canonical_url(source.url) for source in proposal.sources]
    return None if len(set(urls)) == len(urls) else "each source is named once; give all its quotes under it"


class StructureCheck(ContractModel):
    check: Literal[*CHECK_KINDS]
    passed: bool
    reasons: list[str]


class StructureProposalResult(ContractModel):
    schema_version: Literal[1] = STRUCTURE_SCHEMA_VERSION
    outcome: Literal[*STRUCTURE_OUTCOMES]
    proposal_id: uuid.UUID
    status: str
    kind: StructureKind
    subject: StructureSubject
    claim_id: uuid.UUID | None = None
    checks: list[StructureCheck]
    page_url: str
    message: str
