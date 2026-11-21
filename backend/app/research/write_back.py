from __future__ import annotations

import hashlib
import uuid
from collections.abc import Sequence
from decimal import Decimal
from typing import Literal, Protocol, Self, runtime_checkable

from pydantic import Field, field_validator, model_validator

from .base import ContractModel
from .crafts import SLUG_MAX_CHARS
from .evidence import EvidenceItem, Quote, personal_data_in
from .quotes import figures_in, normalise_quote_text, unsupported_figures
from .vocabulary import (
    CONCEPT_TYPE_DISCIPLINES,
    LABEL_LEVELS,
    Discipline,
    EvidenceLabel,
    FacetType,
    QuoteCheck,
    SourceRelation,
)

__all__ = [
    "DEDUPE_NAMESPACE",
    "FOUND_BY",
    "WRITE_BACK_ORIGIN",
    "WRITE_BACK_STATUS",
    "ClaimWriteBack",
    "ClaimWriter",
    "FoundBy",
    "WriteBackCitation",
    "WriteBackResult",
    "WriteBackSubject",
    "claim_dedupe_key",
]

WRITE_BACK_SCHEMA_VERSION = 1
WRITE_BACK_ORIGIN = "LIVE_RESEARCH"
WRITE_BACK_STATUS = "APPROVED"
DEDUPE_NAMESPACE = "claim-write-back/v2"
KEY_SEPARATOR = "\x1f"
FOUND_BY = ("ANSWER", "BACKGROUND")

FoundBy = Literal[*FOUND_BY]


class WriteBackSubject(ContractModel):
    concept_id: uuid.UUID | None = None
    concept_type: FacetType
    concept_name: str = Field(min_length=1, max_length=300)


class WriteBackCitation(ContractModel):
    evidence: EvidenceItem
    quote: Quote | None
    quote_check: QuoteCheck
    relation: SourceRelation

    @model_validator(mode="after")
    def _quote_and_check_agree(self) -> Self:
        if self.quote is None:
            if self.quote_check != "NA":
                raise ValueError("a citation without a quote has quote_check NA")
        elif self.quote_check == "NA":
            raise ValueError("a quoted citation records PASS or FAIL")
        elif self.quote not in self.evidence.quotes:
            raise ValueError("the quote is one of the evidence item's verified quotes")
        return self


class ClaimWriteBack(ContractModel):
    schema_version: Literal[1] = WRITE_BACK_SCHEMA_VERSION
    craft_slug: str | None = Field(min_length=1, max_length=SLUG_MAX_CHARS)
    subject: WriteBackSubject
    field: Discipline | None = None
    predicate: str = Field(min_length=1, max_length=120)
    text: str = Field(min_length=1, max_length=1000)
    text_lang: str = Field(default="en", min_length=2, max_length=16)
    value_num: Decimal | None = None
    value_unit: str | None = Field(default=None, max_length=40)
    label: EvidenceLabel
    level_reason: str = Field(min_length=1, max_length=500)
    citations: list[WriteBackCitation] = Field(min_length=1)
    found_by: FoundBy
    answer_id: uuid.UUID | None = None

    @field_validator("text")
    @classmethod
    def _no_personal_data(cls, value: str) -> str:
        found = personal_data_in(value)
        if found:
            raise ValueError(f"a fact never carries personal data ({', '.join(found)})")
        return value

    @model_validator(mode="after")
    def _provenance_is_whole(self) -> Self:
        if (self.found_by == "ANSWER") != (self.answer_id is not None):
            raise ValueError("an ANSWER write-back names its answer; a BACKGROUND one does not")
        if self.label == "QUOTED" and not self.passing_quotes:
            raise ValueError("a QUOTED claim has at least one quote that passed the check")
        if self.value_unit is not None and self.value_num is None:
            raise ValueError("a unit needs a value")
        return self

    @model_validator(mode="after")
    def _figures_are_quoted(self) -> Self:
        quotes = self.passing_quotes
        missing = unsupported_figures(self.text, quotes)
        if self.value_num is not None:
            value = format(self.value_num.normalize(), "f")
            if value not in {figure for quote in quotes for figure in figures_in(quote)}:
                missing.append(value)
        if missing:
            raise ValueError(f"figures not found in a passing quote: {', '.join(missing)}")
        return self

    @property
    def passing_quotes(self) -> list[str]:
        return [c.quote.text for c in self.citations if c.quote is not None and c.quote_check == "PASS"]

    @property
    def evidence_level(self) -> str:
        return LABEL_LEVELS[self.label]

    @property
    def stored_field(self) -> str | None:
        return self.field or CONCEPT_TYPE_DISCIPLINES.get(self.subject.concept_type)

    @property
    def dedupe_key(self) -> str:
        return claim_dedupe_key(self.craft_slug, self.stored_field, self.text)


class WriteBackResult(ContractModel):
    dedupe_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    claim_id: uuid.UUID
    created: bool


def claim_dedupe_key(craft_slug: str | None, field: str | None, text: str) -> str:
    parts = [DEDUPE_NAMESPACE, craft_slug or "", field or "", _fold(text)]
    return hashlib.sha256(KEY_SEPARATOR.join(parts).encode("utf-8")).hexdigest()


def _fold(text: str) -> str:
    return normalise_quote_text(text).casefold().rstrip(" .")


@runtime_checkable
class ClaimWriter(Protocol):
    async def write(self, claims: Sequence[ClaimWriteBack]) -> list[WriteBackResult]: ...
