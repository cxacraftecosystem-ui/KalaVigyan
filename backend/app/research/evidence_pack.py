from __future__ import annotations

from collections.abc import Sequence
from typing import Literal, Protocol, Self

from pydantic import Field, model_validator

from app.core.errors import FAILURE_KINDS

from .base import URL_MAX_CHARS, ContractModel
from .evidence import EVIDENCE_ID_MAX_CHARS, EvidenceItem, SourceDocument
from .planning import FacetCoverage, RetrievalPlan
from .retrieval import KnowledgeHits

__all__ = [
    "PACK_SCHEMA_VERSION",
    "REFUSED_KIND",
    "RESEARCH_FAILURE_KINDS",
    "RESEARCH_STAGES",
    "EvidencePack",
    "PackedEvidence",
    "ResearchFailure",
    "ResearchTrail",
]

PACK_SCHEMA_VERSION = 1
RESEARCH_STAGES = ("SEARCH", "LOCATE", "FETCH", "FOLLOW")
REFUSED_KIND = "refused"
RESEARCH_FAILURE_KINDS = (*sorted(FAILURE_KINDS), REFUSED_KIND)


class ResearchFailure(ContractModel):
    stage: Literal[*RESEARCH_STAGES]
    service: str = Field(min_length=1, max_length=40)
    target: str = Field(min_length=1, max_length=URL_MAX_CHARS)
    kind: Literal[*RESEARCH_FAILURE_KINDS]
    reason: str | None = Field(default=None, max_length=40)
    message: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def _refusals_carry_a_reason(self) -> Self:
        if (self.kind == REFUSED_KIND) != (self.reason is not None):
            raise ValueError("a refusal, and only a refusal, carries its reason code")
        return self


class PackedEvidence(ContractModel):
    item: EvidenceItem
    facet_indexes: tuple[int, ...] = Field(min_length=1)
    found_by: tuple[str, ...] = Field(min_length=1)
    hits: int = Field(ge=1)
    best_rank: int = Field(ge=1)
    followed_from: str | None = Field(default=None, max_length=EVIDENCE_ID_MAX_CHARS)


class EvidencePack(ContractModel):
    schema_version: Literal[1] = PACK_SCHEMA_VERSION
    plan: RetrievalPlan
    degraded: bool
    stored: KnowledgeHits
    coverage: tuple[FacetCoverage, ...]
    evidence: tuple[PackedEvidence, ...] = ()
    documents: tuple[SourceDocument, ...] = ()
    failures: tuple[ResearchFailure, ...] = ()
    searched: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.stored.craft_slug != (self.plan.craft.slug if self.plan.craft else None):
            raise ValueError("stored knowledge belongs to the planned craft")
        if [entry.facet_index for entry in self.coverage] != list(range(len(self.plan.facets))):
            raise ValueError("coverage lists each planned facet once, in facet order")
        if len(set(self.searched)) != len(self.searched):
            raise ValueError("searched names each live searcher once")
        _check_evidence(self.evidence, len(self.plan.facets))
        _check_documents(self.documents, self.evidence, self.plan.max_fetches)
        return self


def _check_evidence(evidence: tuple[PackedEvidence, ...], facet_count: int) -> None:
    ids = [entry.item.id for entry in evidence]
    keys = [entry.item.source_key for entry in evidence]
    if len(set(ids)) != len(ids) or len(set(keys)) != len(keys):
        raise ValueError("evidence is deduplicated by id and by source key")
    if any(index >= facet_count for entry in evidence for index in entry.facet_indexes):
        raise ValueError("evidence names facets by their index in the plan")
    if any(entry.followed_from is not None and entry.followed_from not in ids for entry in evidence):
        raise ValueError("a followed reference names evidence in the pack")


def _check_documents(
    documents: tuple[SourceDocument, ...], evidence: tuple[PackedEvidence, ...], max_fetches: int
) -> None:
    if len(documents) > max_fetches:
        raise ValueError(f"the plan reads at most {max_fetches} documents")
    ids = [document.item.id for document in documents]
    if len(set(ids)) != len(ids):
        raise ValueError("each evidence item is read once")
    if not set(ids) <= {entry.item.id for entry in evidence}:
        raise ValueError("every document reads an evidence item in the pack")


class ResearchTrail(Protocol):
    async def found(self, evidence: Sequence[PackedEvidence]) -> None: ...

    async def read(self, document: SourceDocument) -> None: ...
