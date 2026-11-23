from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import Refused
from app.models import Claim, ClaimSource, ReviewEvent, Source, StructureProposal, User
from app.research.candidate_gates import QUOTES_GATE, SOURCE_GATE, GateOutcome
from app.research.evidence import canonical_url

from .candidate_writes import record_checks
from .curation_keys import CURATED_PREDICATE, CURATED_STATUS, CURATION_ACTOR, QUOTED_LEVEL, curated_id
from .curation_rows import claim_source_id
from .live_source_store import chunk_for_quote
from .proposal_writes import PROPOSAL_CLAIM_ORIGIN
from .structure_proposals_owner import StructureOwner, claim_marker, taken_claim_keys
from .structure_proposals_page import next_key

__all__ = [
    "CLAIM_LEVEL_REASON",
    "MOVED_SOURCE",
    "ClaimPlan",
    "dossier_marker",
    "write_curated_claim",
]

CLAIM_PREFIX, SOURCE_PREFIX = "C", "S"
CLAIM_WIDTH = 3
OPEN_ACCESS = "OPEN"
COPIED_STORAGE = "EXCERPT"
CONTRIBUTED_ORIGIN = "CONTRIBUTION"
PASSED_QUOTE_CHECK = "PASS"
DIRECT = "DIRECT"
USER_ACTOR = "USER"
MARKER = "curation"
KEPT_GATES = (QUOTES_GATE, SOURCE_GATE)
MOVED_SOURCE = "moved_source"
CLAIM_LEVEL_REASON = "Proposed with a structure entry: every quote was re-found verbatim in its fetched source by the candidate gates"
GONE_SOURCE = (
    "The source {url} this proposal cites is no longer stored. Reject it, and it can be proposed again."
)
SHARED_DOI = (
    "The source {url} is kept by the dossier of {owner} and named there by its DOI, so this dossier cannot keep "
    "a copy of it. Reject it, and it can be proposed citing another source."
)


@dataclass(frozen=True)
class ClaimPlan:
    owner: StructureOwner
    concept_id: uuid.UUID
    version: int
    proposal: StructureProposal


def dossier_marker(source: Source) -> tuple[str | None, str | None]:
    marker = str((source.externalIds or {}).get(MARKER) or "")
    owner, _, key = marker.rpartition(":")
    return (owner, key) if owner and key else (None, None)


async def write_curated_claim(session: AsyncSession, plan: ClaimPlan, reviewer: User) -> uuid.UUID:
    row = plan.proposal
    key = next_key(CLAIM_PREFIX, await taken_claim_keys(session, plan.owner), width=CLAIM_WIDTH)
    claim_id = curated_id(plan.owner.slug, key)
    session.add(_claim(plan, claim_id))
    await session.flush()
    session.add(claim_marker(plan.owner, claim_id, key, row.field))
    await _cite(session, plan, claim_id, key)
    await record_checks(session, claim_id, _kept_outcomes(row.checks), checked_at=row.createdAt)
    session.add(
        ReviewEvent(
            claimId=claim_id,
            actorId=reviewer.id,
            actorKind=USER_ACTOR,
            toStatus=CURATED_STATUS,
            toLevel=QUOTED_LEVEL,
            note=f"structure proposal {row.id} ({row.kind}) approved into the dossier of {plan.owner.slug}",
        )
    )
    await session.flush()
    return claim_id


def _claim(plan: ClaimPlan, claim_id: uuid.UUID) -> Claim:
    row = plan.proposal
    return Claim(
        id=claim_id,
        subjectType="CONCEPT",
        subjectId=plan.concept_id,
        predicate=CURATED_PREDICATE,
        text=row.statement,
        evidenceLevel=QUOTED_LEVEL,
        levelReason=CLAIM_LEVEL_REASON,
        origin=PROPOSAL_CLAIM_ORIGIN,
        status=CURATED_STATUS,
        version=plan.version,
        createdById=row.proposerId,
        createdByKind=USER_ACTOR,
        field=row.field,
        fields=[],
    )


async def _cite(session: AsyncSession, plan: ClaimPlan, claim_id: uuid.UUID, claim_key: str) -> None:
    slug = plan.owner.slug
    taken = await _source_keys(session, slug)
    for stored in plan.proposal.sources:
        source, source_key = await _dossier_source(session, plan, stored, taken)
        taken.append(source_key)
        for quote in stored["quotes"]:
            chunk = await chunk_for_quote(session, source.id, quote["text"])
            session.add(
                ClaimSource(
                    id=claim_source_id(slug, claim_key, source_key, quote["text"]),
                    claimId=claim_id,
                    sourceId=source.id,
                    chunkId=chunk.chunk_id if chunk else None,
                    locator=quote["locator"],
                    quote=quote["text"],
                    quoteCheck=PASSED_QUOTE_CHECK,
                    checkedAt=plan.proposal.createdAt,
                    relation=DIRECT,
                    foundBy=CURATION_ACTOR,
                    retrievedAt=source.retrievedAt,
                )
            )
    await session.flush()


async def _dossier_source(
    session: AsyncSession, plan: ClaimPlan, stored: Mapping[str, Any], taken: Sequence[str]
) -> tuple[Source, str]:
    slug = plan.owner.slug
    source = await session.get(Source, uuid.UUID(str(stored["sourceId"])), with_for_update=True)
    if source is None:
        raise Refused(MOVED_SOURCE, GONE_SOURCE.format(url=stored["url"]))
    owner, key = dossier_marker(source)
    if owner == slug and key is not None:
        return source, key
    own = await _owned_copy(session, slug, source.url or str(stored["url"]))
    if own is not None:
        return own
    key = next_key(SOURCE_PREFIX, taken)
    if owner is None:
        source.externalIds = {**(source.externalIds or {}), **_marker(slug, key, stored)}
        source.retrievedAt = source.retrievedAt or plan.proposal.createdAt
        return source, key
    if source.doi:
        raise Refused(MOVED_SOURCE, SHARED_DOI.format(url=source.url, owner=owner))
    copy = _copied(source, curated_id(slug, key), _marker(slug, key, stored), plan)
    session.add(copy)
    await session.flush()
    return copy, key


def _marker(slug: str, key: str, stored: Mapping[str, Any]) -> dict[str, Any]:
    return {MARKER: f"{slug}:{key}", "language": stored["language"], "access": OPEN_ACCESS}


def _copied(source: Source, source_id: uuid.UUID, external: dict[str, Any], plan: ClaimPlan) -> Source:
    return Source(
        id=source_id,
        kind=source.kind,
        title=source.title,
        authors=list(source.authors or []),
        year=source.year,
        url=source.url,
        publisher=source.publisher,
        licence=source.licence,
        reliability=source.reliability,
        storage=COPIED_STORAGE,
        retrievedAt=source.retrievedAt or plan.proposal.createdAt,
        addedById=plan.proposal.proposerId,
        origin=CONTRIBUTED_ORIGIN,
        sensitivity=source.sensitivity,
        evidenceKind=source.evidenceKind,
        externalIds=external,
    )


async def _source_keys(session: AsyncSession, slug: str) -> list[str]:
    markers = await session.scalars(
        select(Source.externalIds[MARKER].astext).where(Source.externalIds[MARKER].astext.like(f"{slug}:%"))
    )
    return [str(marker).rpartition(":")[2] for marker in markers.all()]


async def _owned_copy(session: AsyncSession, slug: str, url: str) -> tuple[Source, str] | None:
    urls = sorted({url, canonical_url(url)})
    found = await session.scalar(
        select(Source)
        .where(Source.url.in_(urls), Source.externalIds[MARKER].astext.like(f"{slug}:%"))
        .order_by(Source.createdAt, Source.id)
        .limit(1)
    )
    if found is None:
        return None
    _owner, key = dossier_marker(found)
    return (found, key) if key is not None else None


def _kept_outcomes(checks: Sequence[Mapping[str, Any]]) -> list[GateOutcome]:
    return [
        GateOutcome(gate=check["check"], passed=check["passed"], reasons=list(check["reasons"]))
        for check in checks
        if check["check"] in KEPT_GATES
    ]
