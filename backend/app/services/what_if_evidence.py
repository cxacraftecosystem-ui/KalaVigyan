from __future__ import annotations

import uuid
from collections.abc import Collection, Mapping
from dataclasses import dataclass, field

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Claim, ConceptEdge
from app.research.citations import SourceRef
from app.research.retrieval import CLAIM_SUBJECT_TYPES, EVERY_CHUNK_ACLS

from .knowledge_view import ClaimView, claims_by_id, source_ref

__all__ = [
    "CONTRAST_RELATION",
    "OUTCOME_RELATIONS",
    "Relationship",
    "WhatIfEvidence",
    "what_if_evidence",
]

CONCEPT_SUBJECT, EDGE_SUBJECT = CLAIM_SUBJECT_TYPES
CONTRAST_RELATION = "CONTRASTS_WITH"
OUTCOME_RELATIONS = (
    CONTRAST_RELATION,
    "CAUSES",
    "PREVENTS",
    "PRODUCES",
    "ENABLES",
    "MODIFIES",
    "AFFECTED_BY",
    "DEPENDS_ON",
    "REQUIRES",
)


@dataclass(frozen=True)
class Relationship:
    claim_id: uuid.UUID
    relation: str
    concept_ids: frozenset[uuid.UUID]


@dataclass(frozen=True)
class WhatIfEvidence:
    relationships: tuple[Relationship, ...] = ()
    concept_claims: Mapping[uuid.UUID, tuple[uuid.UUID, ...]] = field(default_factory=dict)
    views: Mapping[uuid.UUID, ClaimView] = field(default_factory=dict)
    sources: Mapping[str, SourceRef] = field(default_factory=dict)

    def relationships_of(self, concept_id: uuid.UUID) -> list[Relationship]:
        return [found for found in self.relationships if concept_id in found.concept_ids]


async def what_if_evidence(
    sessions: async_sessionmaker[AsyncSession], concept_ids: Collection[uuid.UUID]
) -> WhatIfEvidence:
    wanted = list(dict.fromkeys(concept_ids))
    if not wanted:
        return WhatIfEvidence()
    async with sessions() as session:
        relationships = await _relationships(session, wanted)
        concept_claims = await _concept_claims(session, wanted)
        claim_ids = [found.claim_id for found in relationships]
        claim_ids += [claim_id for claims in concept_claims.values() for claim_id in claims]
        views, sources = await claims_by_id(session, claim_ids, acls=EVERY_CHUNK_ACLS)
    return WhatIfEvidence(
        relationships=tuple(relationships),
        concept_claims=concept_claims,
        views=views,
        sources={str(sid): SourceRef.model_validate(source_ref(source)) for sid, source in sources.items()},
    )


async def _relationships(session: AsyncSession, concept_ids: list[uuid.UUID]) -> list[Relationship]:
    statement = (
        select(Claim.id, ConceptEdge.relation, ConceptEdge.srcId, ConceptEdge.dstId)
        .join(ConceptEdge, ConceptEdge.id == Claim.subjectId)
        .where(
            Claim.subjectType == EDGE_SUBJECT,
            ConceptEdge.relation.in_(OUTCOME_RELATIONS),
            or_(ConceptEdge.srcId.in_(concept_ids), ConceptEdge.dstId.in_(concept_ids)),
        )
        .order_by(Claim.id)
    )
    rows = (await session.execute(statement)).tuples().all()
    return [Relationship(claim_id, relation, frozenset({src, dst})) for claim_id, relation, src, dst in rows]


async def _concept_claims(
    session: AsyncSession, concept_ids: list[uuid.UUID]
) -> dict[uuid.UUID, tuple[uuid.UUID, ...]]:
    statement = (
        select(Claim.subjectId, Claim.id)
        .where(Claim.subjectType == CONCEPT_SUBJECT, Claim.subjectId.in_(concept_ids))
        .order_by(Claim.subjectId, Claim.id)
    )
    found: dict[uuid.UUID, list[uuid.UUID]] = {}
    for concept_id, claim_id in (await session.execute(statement)).tuples().all():
        found.setdefault(concept_id, []).append(claim_id)
    return {concept_id: tuple(claims) for concept_id, claims in found.items()}
