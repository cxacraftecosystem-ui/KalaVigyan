from __future__ import annotations

import uuid
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import Field, field_validator

from app.core.roles import Capability, can
from app.models.enums import CHUNK_ACLS, CLAIM_STATUSES, EVIDENCE_LEVELS

from .base import ContractModel
from .crafts import QUESTION_MAX_CHARS
from .vocabulary import AnswerMode, ChunkAcl, Discipline, EvidenceLevel, FacetType, SourceType

__all__ = [
    "BROAD_FIELDS",
    "CLAIM_SUBJECT_TYPES",
    "EVERY_CHUNK_ACLS",
    "HIDDEN_CLAIM_STATUSES",
    "KNOWLEDGE_RESULT_MAX",
    "MODE_CLAIM_LEVELS",
    "MODE_CLAIM_STATUSES",
    "OPEN_CHUNK_ACLS",
    "PUBLIC_CHUNK_ACL",
    "RESEARCHER_CHUNK_ACL",
    "RESTRICTED_SENSITIVITY",
    "SIGNED_IN_CHUNK_ACL",
    "SIGNED_IN_CHUNK_ACLS",
    "VISIBLE_SENSITIVITY",
    "ChunkHit",
    "ClaimHit",
    "EnglishRendering",
    "KnowledgeHits",
    "KnowledgeQuery",
    "KnowledgeRetriever",
    "chunk_acls_for",
    "searched_fields",
]

BROAD_FIELDS = ("OVERVIEW",)
KNOWLEDGE_RESULT_MAX = 50
KNOWLEDGE_RESULT_DEFAULT = 12
CLAIM_SUBJECT_TYPES = ("CONCEPT", "EDGE")
HIDDEN_CLAIM_STATUSES = ("DRAFT", "REJECTED", "RETRACTED", "SUPERSEDED", "WITHDRAWN")
VISIBLE_SENSITIVITY = "OPEN"
RESTRICTED_SENSITIVITY = "RESTRICTED"
VERIFIED_MODE_LEVELS = ("VERIFIED", "REVIEWED")
SHOWN_CLAIM_STATUSES = tuple(status for status in CLAIM_STATUSES if status not in HIDDEN_CLAIM_STATUSES)
PUBLIC_CHUNK_ACL: ChunkAcl = "PUBLIC"
RESEARCHER_CHUNK_ACL: ChunkAcl = "RESEARCHER"
SIGNED_IN_CHUNK_ACL: ChunkAcl = "SIGNED_IN"
OPEN_CHUNK_ACLS: tuple[ChunkAcl, ...] = (PUBLIC_CHUNK_ACL,)
SIGNED_IN_CHUNK_ACLS: tuple[ChunkAcl, ...] = (PUBLIC_CHUNK_ACL, SIGNED_IN_CHUNK_ACL)
EVERY_CHUNK_ACLS: tuple[str, ...] = CHUNK_ACLS

MODE_CLAIM_LEVELS: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {"VERIFIED": VERIFIED_MODE_LEVELS, "HYBRID": EVIDENCE_LEVELS, "DEEP": EVIDENCE_LEVELS}
)
MODE_CLAIM_STATUSES: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {"VERIFIED": ("APPROVED",), "HYBRID": SHOWN_CLAIM_STATUSES, "DEEP": SHOWN_CLAIM_STATUSES}
)

ClaimSubjectType = Literal[*CLAIM_SUBJECT_TYPES]


class KnowledgeQuery(ContractModel):
    craft_slug: str | None = Field(min_length=1, max_length=200)
    text: str = Field(min_length=1, max_length=QUESTION_MAX_CHARS)
    mode: AnswerMode
    facets: tuple[FacetType, ...] = ()
    fields: tuple[Discipline, ...] = ()
    chunk_acls: tuple[ChunkAcl, ...] = OPEN_CHUNK_ACLS
    limit: int = Field(default=KNOWLEDGE_RESULT_DEFAULT, ge=1, le=KNOWLEDGE_RESULT_MAX)
    source_kinds: tuple[SourceType, ...] = ()
    passages: bool = True
    rerank: bool = False

    @field_validator("facets", "fields", "chunk_acls", "source_kinds")
    @classmethod
    def _distinct(cls, values: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(values)) != len(values):
            raise ValueError("Each value may appear once")
        return values


class ClaimHit(ContractModel):
    claim_id: uuid.UUID
    text: str = Field(min_length=1)
    level: EvidenceLevel
    subject_type: ClaimSubjectType
    subject_id: uuid.UUID
    score: float = Field(gt=0)
    lexical_rank: int | None = Field(default=None, ge=1)
    vector_rank: int | None = Field(default=None, ge=1)
    entity_rank: int | None = Field(default=None, ge=1)
    relevance_score: float | None = Field(default=None, allow_inf_nan=False)
    corroborating_ids: tuple[uuid.UUID, ...] = ()


class ChunkHit(ContractModel):
    chunk_id: uuid.UUID
    source_id: uuid.UUID
    ordinal: int = Field(ge=0)
    locator: str | None = None
    text: str = Field(min_length=1)
    score: float = Field(gt=0)
    lexical_rank: int | None = Field(default=None, ge=1)
    vector_rank: int | None = Field(default=None, ge=1)
    source_kind: SourceType | None = None
    source_title: str | None = Field(default=None, min_length=1)


class KnowledgeHits(ContractModel):
    craft_slug: str | None
    claims: tuple[ClaimHit, ...] = ()
    chunks: tuple[ChunkHit, ...] = ()


@runtime_checkable
class KnowledgeRetriever(Protocol):
    async def search(self, query: KnowledgeQuery) -> KnowledgeHits: ...


class EnglishRendering(Protocol):
    async def __call__(self, text: str) -> str: ...


def searched_fields(focus: str | None) -> tuple[str, ...]:
    if focus is None or focus in BROAD_FIELDS:
        return ()
    return (focus,)


def chunk_acls_for(reader: Any) -> tuple[str, ...]:
    if reader is not None and can(reader, Capability.READ_RESEARCHER_QUOTES):
        return EVERY_CHUNK_ACLS
    return SIGNED_IN_CHUNK_ACLS
