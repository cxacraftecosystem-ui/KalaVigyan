from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Literal

from sqlalchemy import ColumnElement, Select, and_, exists, or_, select
from sqlalchemy.orm import aliased

from app.models import Chunk, Claim, ClaimSource, Concept, ConceptEdge, Source
from app.research.retrieval import RESTRICTED_SENSITIVITY, SHOWN_CLAIM_STATUSES, VISIBLE_SENSITIVITY

from .field_scope import withheld_field_sources

__all__ = [
    "CONCEPT_SUBJECT",
    "EDGE_SUBJECT",
    "FAILED_QUOTE",
    "HELD_KEPT",
    "HELD_LEFT_OUT",
    "READABLE",
    "HeldFacts",
    "cited_for_readers",
    "filed_for_readers",
    "held_claim",
    "readable_citation",
    "reader_citations",
    "reader_fact",
    "shown_source",
    "unheld",
]

FAILED_QUOTE = "FAIL"
CONCEPT_SUBJECT = "CONCEPT"
EDGE_SUBJECT = "EDGE"
READABLE = "readable"

type HeldFacts = Literal["LEFT_OUT", "KEPT"]
HELD_LEFT_OUT: HeldFacts = "LEFT_OUT"
HELD_KEPT: HeldFacts = "KEPT"


def held_claim() -> ColumnElement[bool]:
    quoted = ClaimSource.quote.is_not(None)
    cited = exists().where(ClaimSource.claimId == Claim.id, quoted)
    standing = exists().where(ClaimSource.claimId == Claim.id, quoted, ClaimSource.quoteCheck != FAILED_QUOTE)
    return and_(cited, ~standing)


def unheld(held: HeldFacts) -> list[ColumnElement[bool]]:
    return [] if held == HELD_KEPT else [~held_claim()]


def reader_fact(
    held: HeldFacts = HELD_LEFT_OUT, *, statuses: Sequence[str] = SHOWN_CLAIM_STATUSES
) -> list[ColumnElement[bool]]:
    hidden = set(statuses) - set(SHOWN_CLAIM_STATUSES)
    if hidden:
        raise ValueError(f"a reader never sees a fact {', '.join(sorted(hidden))}")
    return [
        Claim.status.in_(list(statuses)),
        Claim.sensitivity == VISIBLE_SENSITIVITY,
        filed_for_readers(),
        cited_for_readers(),
        *unheld(held),
    ]


def shown_source() -> ColumnElement[bool]:
    return and_(Source.sensitivity != RESTRICTED_SENSITIVITY, Source.id.not_in(withheld_field_sources()))


def cited_for_readers() -> ColumnElement[bool]:
    cite = aliased(ClaimSource, name="reader_cite")
    shown = aliased(Source, name="reader_source")
    return (
        select(cite.id)
        .join(shown, shown.id == cite.sourceId)
        .where(
            cite.claimId == Claim.id,
            shown.sensitivity != RESTRICTED_SENSITIVITY,
            shown.id.not_in(withheld_field_sources()),
        )
        .correlate(Claim)
        .exists()
    )


def filed_for_readers() -> ColumnElement[bool]:
    concept = aliased(Concept, name="reader_concept")
    direct = select(concept.id).where(
        concept.id == Claim.subjectId, concept.sensitivity == VISIBLE_SENSITIVITY
    )
    edge = aliased(ConceptEdge, name="reader_edge")
    linked = (
        select(edge.id)
        .join(concept, or_(concept.id == edge.srcId, concept.id == edge.dstId))
        .where(edge.id == Claim.subjectId, concept.sensitivity == VISIBLE_SENSITIVITY)
    )
    return or_(
        and_(Claim.subjectType == CONCEPT_SUBJECT, direct.correlate(Claim).exists()),
        and_(Claim.subjectType == EDGE_SUBJECT, linked.correlate(Claim).exists()),
    )


def reader_citations(
    claim_ids: Sequence[uuid.UUID], *, acls: Sequence[str]
) -> Select[tuple[ClaimSource, bool]]:
    return (
        select(ClaimSource, readable_citation(acls).label(READABLE))
        .join(Source, Source.id == ClaimSource.sourceId)
        .where(ClaimSource.claimId.in_(list(claim_ids)), shown_source())
    )


def readable_citation(acls: Sequence[str]) -> ColumnElement[bool]:
    allowed = list(acls)
    linked = (
        select(Chunk.id)
        .where(
            Chunk.id == ClaimSource.chunkId,
            Chunk.acl.in_(allowed),
            Chunk.sensitivity != RESTRICTED_SENSITIVITY,
        )
        .correlate(ClaimSource)
        .exists()
    )
    unlinked = and_(
        ClaimSource.chunkId.is_(None),
        or_(ClaimSource.quote.is_(None), _every_passage_readable(allowed)),
    )
    return or_(linked, unlinked)


def _every_passage_readable(acls: list[str]) -> ColumnElement[bool]:
    closed = (
        select(Chunk.id)
        .where(
            Chunk.sourceId == ClaimSource.sourceId,
            or_(Chunk.acl.not_in(acls), Chunk.sensitivity == RESTRICTED_SENSITIVITY),
        )
        .correlate(ClaimSource)
        .exists()
    )
    restricted = (
        select(Source.id)
        .where(Source.id == ClaimSource.sourceId, Source.sensitivity == RESTRICTED_SENSITIVITY)
        .correlate(ClaimSource)
        .exists()
    )
    return and_(~closed, ~restricted)
