from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from itertools import batched
from typing import Any

from sqlalchemy import and_, delete, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Claim, ClaimSource, Concept, Craft, SharedTermCraft, Term, TermConcept, TermCraft
from app.research.blocks import named_in_texts
from app.research.blocks_learning import COMPARE_CRAFTS_MIN
from app.research.retrieval import HIDDEN_CLAIM_STATUSES, VISIBLE_SENSITIVITY
from app.research.vocabulary import FACT_LEVELS
from app.retrieval.citation_access import FAILED_QUOTE

__all__ = [
    "IDS_PER_QUERY",
    "TERMS_PER_BATCH",
    "ConceptClaim",
    "ConceptLink",
    "SharedTermsReport",
    "TermCrafts",
    "refresh_shared_terms",
    "shared_term_crafts",
    "stored_term_crafts",
]

TERMS_PER_BATCH = 200
IDS_PER_QUERY = 1000
MERGED = "MERGED"
CONCEPT_SUBJECT = "CONCEPT"


@dataclass(frozen=True)
class ConceptLink:
    term_id: uuid.UUID
    craft_id: uuid.UUID
    concept_id: uuid.UUID


@dataclass(frozen=True)
class ConceptClaim:
    concept_id: uuid.UUID
    claim_id: uuid.UUID
    texts: tuple[str, ...]


@dataclass(frozen=True)
class TermCrafts:
    term_id: uuid.UUID
    craft_id: uuid.UUID
    concept_ids: tuple[uuid.UUID, ...]
    claim_ids: tuple[uuid.UUID, ...]


@dataclass
class SharedTermsReport:
    terms: int = 0
    crafts: int = 0

    def as_dict(self) -> dict[str, int]:
        return {"terms": self.terms, "crafts": self.crafts}


def shared_term_crafts(
    labels: Mapping[uuid.UUID, str], links: Sequence[ConceptLink], claims: Sequence[ConceptClaim]
) -> list[TermCrafts]:
    about: dict[uuid.UUID, list[ConceptClaim]] = defaultdict(list)
    for claim in claims:
        about[claim.concept_id].append(claim)
    owned: dict[tuple[uuid.UUID, uuid.UUID], list[uuid.UUID]] = defaultdict(list)
    for link in links:
        owned[(link.term_id, link.craft_id)].append(link.concept_id)
    found: dict[uuid.UUID, list[TermCrafts]] = defaultdict(list)
    for (term_id, craft_id), concepts in owned.items():
        naming = {
            claim.claim_id
            for concept_id in concepts
            for claim in about[concept_id]
            if named_in_texts(labels[term_id], claim.texts)
        }
        if naming:
            found[term_id].append(
                TermCrafts(term_id, craft_id, tuple(dict.fromkeys(concepts)), tuple(sorted(naming)))
            )
    return [row for rows in found.values() if len(rows) >= COMPARE_CRAFTS_MIN for row in rows]


async def refresh_shared_terms(session: AsyncSession, *, now: datetime) -> SharedTermsReport:
    rows: list[TermCrafts] = []
    for batch in batched(await _shared_term_ids(session), TERMS_PER_BATCH, strict=False):
        rows += await _batch_crafts(session, batch)
    await session.execute(delete(SharedTermCraft))
    for chunk in batched(rows, IDS_PER_QUERY, strict=False):
        await session.execute(insert(SharedTermCraft), [_stored(row, now) for row in chunk])
    return SharedTermsReport(terms=len({row.term_id for row in rows}), crafts=len(rows))


async def stored_term_crafts(session: AsyncSession, term_ids: Sequence[uuid.UUID]) -> list[TermCrafts]:
    if not term_ids:
        return []
    rows = await session.scalars(
        select(SharedTermCraft)
        .join(Craft, Craft.id == SharedTermCraft.craftId)
        .where(SharedTermCraft.termId.in_(list(term_ids)), Craft.status != MERGED)
        .order_by(SharedTermCraft.termId, SharedTermCraft.craftId)
    )
    return [
        TermCrafts(row.termId, row.craftId, tuple(row.conceptIds), tuple(row.claimIds)) for row in rows.all()
    ]


async def _shared_term_ids(session: AsyncSession) -> list[uuid.UUID]:
    rows = await session.scalars(
        select(TermConcept.termId)
        .join(Concept, Concept.id == TermConcept.conceptId)
        .group_by(TermConcept.termId)
        .having(func.count(func.distinct(Concept.craftId)) >= COMPARE_CRAFTS_MIN)
        .order_by(TermConcept.termId)
    )
    return list(rows)


async def _batch_crafts(session: AsyncSession, term_ids: Sequence[uuid.UUID]) -> list[TermCrafts]:
    labels = await session.execute(select(Term.id, Term.label).where(Term.id.in_(list(term_ids))))
    links = await _concept_links(session, term_ids)
    claims = await _concept_claims(session, [link.concept_id for link in links])
    return shared_term_crafts(dict(labels.tuples().all()), links, claims)


async def _concept_links(session: AsyncSession, term_ids: Sequence[uuid.UUID]) -> list[ConceptLink]:
    rows = await session.execute(
        select(TermConcept.termId, Concept.craftId, Concept.id)
        .join(Concept, Concept.id == TermConcept.conceptId)
        .join(TermCraft, and_(TermCraft.termId == TermConcept.termId, TermCraft.craftId == Concept.craftId))
        .join(Craft, Craft.id == Concept.craftId)
        .where(
            TermConcept.termId.in_(list(term_ids)),
            Concept.sensitivity == VISIBLE_SENSITIVITY,
            Craft.status != MERGED,
        )
        .order_by(TermConcept.termId, Concept.craftId, Concept.name, Concept.id)
    )
    return [
        ConceptLink(term_id, craft_id, concept_id)
        for term_id, craft_id, concept_id in rows.tuples()
        if craft_id is not None
    ]


async def _concept_claims(session: AsyncSession, concept_ids: Sequence[uuid.UUID]) -> list[ConceptClaim]:
    found: list[Any] = []
    for chunk in batched(dict.fromkeys(concept_ids), IDS_PER_QUERY, strict=False):
        rows = await session.execute(
            select(Claim.id, Claim.subjectId, Claim.text).where(
                Claim.subjectType == CONCEPT_SUBJECT,
                Claim.subjectId.in_(list(chunk)),
                Claim.status.not_in(HIDDEN_CLAIM_STATUSES),
                Claim.sensitivity == VISIBLE_SENSITIVITY,
                Claim.evidenceLevel.in_(FACT_LEVELS),
            )
        )
        found += rows.all()
    quotes = await _quotes(session, [row.id for row in found])
    return [ConceptClaim(row.subjectId, row.id, (row.text, *quotes.get(row.id, ()))) for row in found]


async def _quotes(session: AsyncSession, claim_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, list[str]]:
    quotes: dict[uuid.UUID, list[str]] = defaultdict(list)
    for chunk in batched(claim_ids, IDS_PER_QUERY, strict=False):
        rows = await session.execute(
            select(ClaimSource.claimId, ClaimSource.quote).where(
                ClaimSource.claimId.in_(list(chunk)),
                ClaimSource.quote.is_not(None),
                ClaimSource.quoteCheck != FAILED_QUOTE,
            )
        )
        for claim_id, quote in rows.tuples():
            if quote is not None:
                quotes[claim_id].append(quote)
    return quotes


def _stored(row: TermCrafts, now: datetime) -> dict[str, Any]:
    return {
        "termId": row.term_id,
        "craftId": row.craft_id,
        "conceptIds": list(row.concept_ids),
        "claimIds": list(row.claim_ids),
        "refreshedAt": now,
    }
