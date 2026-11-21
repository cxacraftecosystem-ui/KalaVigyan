from __future__ import annotations

import asyncio
import uuid
from collections.abc import Sequence

from app.research.planning import COVERING_LEVELS, Facet, FacetCoverage
from app.research.retrieval import KnowledgeHits, KnowledgeQuery, KnowledgeRetriever

from .policy import COVERAGE_QUERY_LIMIT, STORED_PACK_LIMIT

__all__ = ["covering_claims", "facet_coverage", "facet_query", "stored_knowledge"]


async def facet_coverage(
    retriever: KnowledgeRetriever, *, craft_slug: str | None, mode: str, facets: Sequence[Facet]
) -> tuple[FacetCoverage, ...]:
    found = await asyncio.gather(
        *(retriever.search(facet_query(craft_slug, mode, facet)) for facet in facets)
    )
    return tuple(
        FacetCoverage(facet_index=index, claim_ids=covering_claims(hits, mode=mode))
        for index, hits in enumerate(found)
    )


def facet_query(craft_slug: str | None, mode: str, facet: Facet) -> KnowledgeQuery:
    return KnowledgeQuery(
        craft_slug=craft_slug,
        text=facet.target,
        mode=mode,
        facets=(facet.type,),
        passages=False,
        limit=COVERAGE_QUERY_LIMIT,
    )


def covering_claims(hits: KnowledgeHits, *, mode: str) -> tuple[uuid.UUID, ...]:
    levels = COVERING_LEVELS[mode]
    return tuple(hit.claim_id for hit in hits.claims if hit.lexical_rank is not None and hit.level in levels)


async def stored_knowledge(
    retriever: KnowledgeRetriever,
    *,
    craft_slug: str | None,
    mode: str,
    question: str,
    fields: Sequence[str] = (),
    limit: int = STORED_PACK_LIMIT,
) -> KnowledgeHits:
    return await retriever.search(
        KnowledgeQuery(
            craft_slug=craft_slug, text=question, mode=mode, fields=tuple(fields), limit=limit, rerank=True
        )
    )
