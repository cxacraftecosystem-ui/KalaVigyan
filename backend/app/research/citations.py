from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Protocol, Self

from pydantic import Field, model_validator

from app.models.knowledge import CONTAINER_TITLE_CHARS, QUOTE_MAX_CHARS

from .base import ContractModel, HttpsUrl, absent
from .vocabulary import EvidenceLabel, ShownLevel, SourceType, TrustTier

__all__ = [
    "AnswerSentence",
    "Citation",
    "Cited",
    "SourceCitation",
    "SourceRef",
    "cited_source_ids",
]


class SourceRef(ContractModel):
    id: str = Field(min_length=1)
    kind: SourceType
    title: str = Field(min_length=1)
    authors: list[str]
    year: int | None
    doi: str | None
    url: HttpsUrl | None
    publisher: str | None
    licence: str | None
    attribution: str | None
    reliability: TrustTier | None
    container_title: str | None = Field(
        default=None, min_length=1, max_length=CONTAINER_TITLE_CHARS, exclude_if=absent
    )


class Citation(ContractModel):
    id: str = Field(min_length=1)
    claim_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    quote: str | None = Field(max_length=QUOTE_MAX_CHARS)
    locator: str | None
    context: str | None
    evidence: EvidenceLabel
    level: ShownLevel


class AnswerSentence(ContractModel):
    id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    level: ShownLevel
    citations: list[Citation] = Field(min_length=1)
    translated: bool = False
    original: str | None = Field(default=None, min_length=1, exclude_if=absent)

    @model_validator(mode="after")
    def _translation_keeps_its_original(self) -> Self:
        if self.translated != (self.original is not None):
            raise ValueError("a translated sentence, and only a translated one, carries its original")
        return self


class SourceCitation(Protocol):
    @property
    def source_id(self) -> str: ...


class Cited(Protocol):
    @property
    def citations(self) -> Sequence[SourceCitation]: ...


def cited_source_ids(cited: Iterable[Cited]) -> list[str]:
    ordered: dict[str, None] = {}
    for item in cited:
        ordered.update((citation.source_id, None) for citation in item.citations)
    return list(ordered)
