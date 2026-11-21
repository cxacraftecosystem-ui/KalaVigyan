from __future__ import annotations

from collections.abc import Sequence
from typing import Literal

from sqlalchemy import ColumnElement, and_, exists, or_, select

from app.models import Chunk, Claim, ClaimSource, Source
from app.research.retrieval import RESTRICTED_SENSITIVITY

__all__ = [
    "FAILED_QUOTE",
    "HELD_KEPT",
    "HELD_LEFT_OUT",
    "HeldFacts",
    "held_claim",
    "readable_citation",
    "unheld",
]

FAILED_QUOTE = "FAIL"

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
