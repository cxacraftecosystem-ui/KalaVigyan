from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import CandidateCheck, Claim, ClaimSource, Concept, Craft, Source
from app.research.candidate_gates import GATES
from app.research.crafts import CraftRef
from app.research.review_queue import (
    FactConcept,
    FactItem,
    FactReview,
    FactSource,
    GateCheck,
    RelatedFact,
    SourceQuote,
    fact_origin,
)

from .claim_holds_review import hold_evidence, with_hold_evidence
from .knowledge_view import craft_ref
from .review_queue_select import Rendered, rows_by_id

__all__ = ["fact_items"]

CONCEPT_SUBJECT = "CONCEPT"


@dataclass(frozen=True)
class _Context:
    concepts: Mapping[uuid.UUID, Concept]
    crafts: Mapping[uuid.UUID, Craft]
    sources: Mapping[uuid.UUID, list[FactSource]]
    found_by: Mapping[uuid.UUID, set[str | None]]
    checks: Mapping[uuid.UUID, list[GateCheck]]


async def fact_items(session: AsyncSession, ids: Sequence[uuid.UUID]) -> list[Rendered]:
    claims = list(await session.scalars(select(Claim).where(Claim.id.in_(list(ids)))))
    concepts = await rows_by_id(
        session, Concept, [c.subjectId for c in claims if c.subjectType == CONCEPT_SUBJECT]
    )
    context = _Context(
        concepts=concepts,
        crafts=await rows_by_id(session, Craft, [concept.craftId for concept in concepts.values()]),
        sources=await _sources(session, ids),
        found_by=await _found_by(session, ids),
        checks=with_hold_evidence(await _checks(session, ids), await hold_evidence(session, ids)),
    )
    return [Rendered(_item(claim, context), claim.createdById) for claim in claims]


def _item(claim: Claim, context: _Context) -> FactItem:
    concept = context.concepts.get(claim.subjectId) if claim.subjectType == CONCEPT_SUBJECT else None
    craft = context.crafts.get(concept.craftId) if concept is not None and concept.craftId else None
    return FactItem(
        id=claim.id,
        origin=fact_origin(claim.origin, context.found_by.get(claim.id, set())),
        submitted_at=claim.createdAt,
        craft=CraftRef.model_validate(craft_ref(craft)) if craft is not None else None,
        fact=FactReview(
            statement=claim.text,
            field=claim.field,
            fields=list(claim.fields or []),
            status=claim.status,
            level=claim.evidenceLevel,
            sources_differ=claim.sourcesDiffer,
            concept=FactConcept(name=concept.name, type=concept.type) if concept is not None else None,
            sources=context.sources.get(claim.id, []),
            gates=context.checks.get(claim.id, []),
        ),
    )


async def _sources(session: AsyncSession, ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, list[FactSource]]:
    rows = await session.execute(
        select(ClaimSource, Source)
        .join(Source, Source.id == ClaimSource.sourceId)
        .where(ClaimSource.claimId.in_(list(ids)))
        .order_by(ClaimSource.claimId, ClaimSource.createdAt, ClaimSource.id)
    )
    grouped: dict[uuid.UUID, dict[uuid.UUID, tuple[Source, list[SourceQuote]]]] = defaultdict(dict)
    for cite, source in rows.all():
        _, quotes = grouped[cite.claimId].setdefault(source.id, (source, []))
        if cite.quote:
            quotes.append(SourceQuote(text=cite.quote, locator=cite.locator))
    return {
        claim_id: [_source(*pair) for pair in by_source.values()] for claim_id, by_source in grouped.items()
    }


def _source(source: Source, quotes: list[SourceQuote]) -> FactSource:
    return FactSource(
        title=source.title,
        url=source.url,
        licence=source.licence,
        reliability=source.reliability,
        quotes=quotes,
    )


async def _found_by(session: AsyncSession, ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, set[str | None]]:
    rows = await session.execute(
        select(ClaimSource.claimId, ClaimSource.foundBy).where(ClaimSource.claimId.in_(list(ids))).distinct()
    )
    found: dict[uuid.UUID, set[str | None]] = defaultdict(set)
    for claim_id, found_by in rows.all():
        found[claim_id].add(found_by)
    return found


async def _checks(session: AsyncSession, ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, list[GateCheck]]:
    rows = list(await session.scalars(select(CandidateCheck).where(CandidateCheck.claimId.in_(list(ids)))))
    texts = await _texts(session, (related for row in rows for related in row.relatedClaimIds))
    checks: dict[uuid.UUID, list[CandidateCheck]] = defaultdict(list)
    for row in rows:
        checks[row.claimId].append(row)
    return {
        claim_id: [_check(row, texts) for row in sorted(found, key=lambda row: GATES.index(row.gate))]
        for claim_id, found in checks.items()
    }


def _check(row: CandidateCheck, texts: Mapping[uuid.UUID, str]) -> GateCheck:
    return GateCheck(
        gate=row.gate,
        passed=row.passed,
        reasons=list(row.reasons),
        model=row.model,
        related=[
            RelatedFact(id=related, text=texts[related])
            for related in row.relatedClaimIds
            if related in texts
        ],
    )


async def _texts(session: AsyncSession, ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, str]:
    wanted = list(dict.fromkeys(ids))
    if not wanted:
        return {}
    rows = await session.execute(select(Claim.id, Claim.text).where(Claim.id.in_(wanted)))
    return dict(rows.tuples().all())
