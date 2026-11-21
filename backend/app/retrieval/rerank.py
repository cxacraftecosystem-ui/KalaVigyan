from __future__ import annotations

import logging
import re
import unicodedata
import uuid
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.errors import AppError
from app.models import Claim, Concept, Craft
from app.research.reranking import Relevance, Reranker, checked_relevance
from app.research.retrieval import ClaimHit

from .text import document_text

__all__ = [
    "RERANK_POOL",
    "RESTATEMENT_COSINE",
    "TITLE_SEPARATOR",
    "RerankCandidates",
    "claim_title",
    "collapsed",
    "folded_words",
    "pool_size",
    "rerank_candidates",
    "reranked",
]

logger = logging.getLogger(__name__)

RERANK_POOL = 60
RESTATEMENT_COSINE = 0.97
TITLE_SEPARATOR = ", "
WORD = re.compile(r"[^\W_]+")


@dataclass(frozen=True)
class RerankCandidates:
    documents: Mapping[uuid.UUID, str] = field(default_factory=dict)
    restated: frozenset[frozenset[uuid.UUID]] = frozenset()


def pool_size(limit: int) -> int:
    return max(limit, RERANK_POOL)


def folded_words(text: str) -> str:
    return " ".join(WORD.findall(unicodedata.normalize("NFKC", text).casefold()))


def claim_title(craft: str | None, concept: str | None, field_name: str | None) -> str | None:
    parts = [part.strip() for part in (craft, concept, (field_name or "").lower()) if part and part.strip()]
    return TITLE_SEPARATOR.join(dict.fromkeys(parts)) or None


async def rerank_candidates(session: AsyncSession, hits: Sequence[ClaimHit]) -> RerankCandidates:
    if not hits:
        return RerankCandidates()
    ids = [hit.claim_id for hit in hits]
    rows = await session.execute(
        select(Claim.id, Claim.field, Concept.name.label("concept"), Craft.name.label("craft"))
        .outerjoin(Concept, Concept.id == Claim.subjectId)
        .outerjoin(Craft, Craft.id == Concept.craftId)
        .where(Claim.id.in_(ids))
    )
    titles = {row.id: claim_title(row.craft, row.concept, row.field) for row in rows}
    documents = {hit.claim_id: document_text(hit.text, title=titles.get(hit.claim_id)) for hit in hits}
    return RerankCandidates(documents, await _restated(session, ids))


async def reranked(
    hits: Sequence[ClaimHit], candidates: RerankCandidates, *, query: str, rerank: Reranker | None
) -> list[ClaimHit]:
    if rerank is None or not hits:
        return list(hits)
    documents = [candidates.documents.get(hit.claim_id) or document_text(hit.text) for hit in hits]
    try:
        found = checked_relevance(await rerank(query, documents), documents=len(documents))
    except AppError as failure:
        logger.warning("the search keeps its fused order: reranking failed (%s)", _kind(failure))
        return list(hits)
    return _in_relevance_order(hits, found)


def collapsed(
    hits: Sequence[ClaimHit], restated: Collection[frozenset[uuid.UUID]], *, limit: int
) -> list[ClaimHit]:
    folded = {hit.claim_id: folded_words(hit.text) for hit in hits}

    def restates(first: uuid.UUID, second: uuid.UUID) -> bool:
        return folded[first] == folded[second] or frozenset((first, second)) in restated

    groups: list[list[uuid.UUID]] = []
    heads: dict[uuid.UUID, ClaimHit] = {}
    for hit in hits:
        group = next((ids for ids in groups if any(restates(kept, hit.claim_id) for kept in ids)), None)
        if group is not None:
            group.append(hit.claim_id)
        elif len(groups) < limit:
            groups.append([hit.claim_id])
            heads[hit.claim_id] = hit
    return [_with_corroboration(heads[ids[0]], ids[1:]) for ids in groups]


def _in_relevance_order(hits: Sequence[ClaimHit], found: Sequence[Relevance]) -> list[ClaimHit]:
    scored = [hits[item.index].model_copy(update={"relevance_score": item.score}) for item in found]
    seen = {item.index for item in found}
    return [*scored, *(hit for index, hit in enumerate(hits) if index not in seen)]


def _with_corroboration(head: ClaimHit, others: Sequence[uuid.UUID]) -> ClaimHit:
    if not others:
        return head
    ids = tuple(dict.fromkeys((*head.corroborating_ids, *others)))
    return head.model_copy(update={"corroborating_ids": ids})


async def _restated(session: AsyncSession, ids: Sequence[uuid.UUID]) -> frozenset[frozenset[uuid.UUID]]:
    if len(ids) < 2:
        return frozenset()
    first, second = aliased(Claim), aliased(Claim)
    rows = await session.execute(
        select(first.id, second.id).where(
            first.id.in_(list(ids)),
            second.id.in_(list(ids)),
            first.id < second.id,
            first.embedding.is_not(None),
            second.embedding.is_not(None),
            first.embeddingModel == second.embeddingModel,
            first.embedding.cosine_distance(second.embedding) <= 1 - RESTATEMENT_COSINE,
        )
    )
    return frozenset(frozenset(pair) for pair in rows.tuples())


def _kind(failure: AppError) -> str:
    return str(getattr(failure, "kind", None) or type(failure).__name__)
