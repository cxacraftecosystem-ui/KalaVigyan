from __future__ import annotations

import asyncio
import uuid
from collections.abc import Sequence

from sqlalchemy import ColumnElement, Select, not_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db import release_connection
from app.core.errors import InvalidInput
from app.models import Chunk, Claim, Craft, CraftSubCategory, Source
from app.research.embedding import TextEmbedder, checked_vectors
from app.research.planning import MODE_POLICIES
from app.research.reranking import Reranker
from app.research.retrieval import ChunkHit, ClaimHit, EnglishRendering, KnowledgeHits, KnowledgeQuery

from .answer_embeddings import AnswerEmbeddings
from .fusion import FusedItem, fused_order, reciprocal_rank_fusion
from .fusion_settings import FusionSettings, fusion_settings
from .rerank import RerankCandidates, collapsed, pool_size, rerank_candidates, reranked
from .statements import (
    EVERY_CRAFT,
    CraftScope,
    chunk_conditions,
    chunk_lexical_ranking,
    chunk_vector_ranking,
    cited_from_kinds,
    claim_conditions,
    claim_entity_ranking,
    claim_lexical_ranking,
    claim_vector_ranking,
    field_passages,
)
from .text import or_tsquery, query_text

__all__ = [
    "CORPUS_TIER",
    "MERGE_HOPS_MAX",
    "ClaimRankings",
    "SessionScopedSearch",
    "StoredKnowledgeSearch",
    "craft_scope",
    "merged_into",
    "search_words",
]

CORPUS_TIER = "T2"
SCORE_DIGITS = 9
RANK_FIELDS = ("lexical_rank", "vector_rank", "entity_rank")
MERGE_HOPS_MAX = 5

ClaimRankings = tuple[list[uuid.UUID], ...]


class SessionScopedSearch:
    def __init__(
        self,
        sessions: async_sessionmaker[AsyncSession],
        *,
        embed: TextEmbedder,
        english: EnglishRendering | None = None,
        rerank: Reranker | None = None,
    ) -> None:
        self._sessions = sessions
        self._embed = embed
        self._english = english
        self._rerank = rerank

    async def search(self, query: KnowledgeQuery) -> KnowledgeHits:
        async with self._sessions() as session:
            stored = StoredKnowledgeSearch(
                session, embed=self._embed, english=self._english, rerank=self._rerank
            )
            return await stored.search(query)

    async def prepare(self, texts: Sequence[str]) -> None:
        if isinstance(self._embed, AnswerEmbeddings):
            await self._embed([query_text(text) for text in texts])

    async def rankings(self, query: KnowledgeQuery) -> ClaimRankings:
        async with self._sessions() as session:
            stored = StoredKnowledgeSearch(session, embed=self._embed, english=self._english)
            return await stored.rankings(query)


class StoredKnowledgeSearch:
    def __init__(
        self,
        session: AsyncSession,
        *,
        embed: TextEmbedder,
        english: EnglishRendering | None = None,
        rerank: Reranker | None = None,
        fusion: FusionSettings | None = None,
    ) -> None:
        self._session = session
        self._embed = embed
        self._english = english
        self._rerank = rerank
        self._fusion = fusion if fusion is not None else fusion_settings()
        self._turn = asyncio.Lock()

    async def search(self, query: KnowledgeQuery) -> KnowledgeHits:
        words, vector = await self._asked(query)
        async with self._turn:
            found = await self._searched(query, words, vector)
            candidates = await self._candidates(query, found)
        if candidates is None:
            return found
        ordered = await reranked(found.claims, candidates, query=words, rerank=self._rerank)
        kept = collapsed(ordered, candidates.restated, limit=query.limit)
        return found.model_copy(update={"claims": tuple(kept)})

    async def _candidates(self, query: KnowledgeQuery, found: KnowledgeHits) -> RerankCandidates | None:
        if not query.rerank:
            return None
        candidates = await rerank_candidates(self._session, found.claims)
        if self._rerank is not None:
            await release_connection(self._session)
        return candidates

    async def rankings(self, query: KnowledgeQuery) -> ClaimRankings:
        words, vector = await self._asked(query)
        async with self._turn:
            scope = await craft_scope(self._session, query.craft_slug)
            return await self._claim_rankings(query, scope, words, vector)

    async def _asked(self, query: KnowledgeQuery) -> tuple[str, list[float]]:
        words = await search_words(query.text, self._english)
        (vector,) = checked_vectors(await self._embed([query_text(query.text)]), expected=1)
        return words, vector

    async def _claim_rankings(
        self, query: KnowledgeQuery, scope: CraftScope, words: str, vector: list[float]
    ) -> ClaimRankings:
        tsquery = or_tsquery(words)
        conditions = _claim_conditions(query, scope)
        return await self._ranked(
            [
                claim_lexical_ranking(conditions, tsquery) if tsquery else None,
                claim_vector_ranking(conditions, vector),
                claim_entity_ranking(conditions, scope, words),
            ]
        )

    async def _searched(self, query: KnowledgeQuery, words: str, vector: list[float]) -> KnowledgeHits:
        scope = await craft_scope(self._session, query.craft_slug)
        tsquery = or_tsquery(words)
        claims = reciprocal_rank_fusion(
            await self._claim_rankings(query, scope, words, vector),
            k=self._fusion.k,
            weights=self._fusion.claims.ordered(),
        )[: pool_size(query.limit) if query.rerank else query.limit]
        chunks: list[FusedItem[uuid.UUID]] = []
        if query.passages and CORPUS_TIER in MODE_POLICIES[query.mode].tiers:
            chunks = await self._passages(query, scope, tsquery, vector)
        return KnowledgeHits(
            craft_slug=query.craft_slug,
            claims=tuple(await self._claim_hits(claims)),
            chunks=tuple(await self._chunk_hits(chunks)),
        )

    async def _passages(
        self, query: KnowledgeQuery, scope: CraftScope, tsquery: str | None, vector: list[float]
    ) -> list[FusedItem[uuid.UUID]]:
        conditions = chunk_conditions(
            scope, mode=query.mode, facets=query.facets, fields=query.fields, acls=query.chunk_acls
        )
        found: list[FusedItem[uuid.UUID]] = []
        for kind in (not_(field_passages()), field_passages()):
            scoped: list[ColumnElement[bool]] = [*conditions, kind]
            found += await self._fuse(
                [
                    chunk_lexical_ranking(scoped, tsquery) if tsquery else None,
                    chunk_vector_ranking(scoped, vector),
                ],
                limit=query.limit,
            )
        return sorted(found, key=fused_order)

    async def _fuse(
        self, rankings: Sequence[Select[tuple[uuid.UUID]] | None], *, limit: int
    ) -> list[FusedItem[uuid.UUID]]:
        return reciprocal_rank_fusion(await self._ranked(rankings))[:limit]

    async def _ranked(self, rankings: Sequence[Select[tuple[uuid.UUID]] | None]) -> ClaimRankings:
        return tuple(
            [
                list((await self._session.scalars(ranking)).all()) if ranking is not None else []
                for ranking in rankings
            ]
        )

    async def _claim_hits(self, fused: Sequence[FusedItem[uuid.UUID]]) -> list[ClaimHit]:
        if not fused:
            return []
        columns = (Claim.id, Claim.text, Claim.evidenceLevel, Claim.subjectType, Claim.subjectId)
        rows = await self._session.execute(select(*columns).where(Claim.id.in_([item.key for item in fused])))
        by_id = {row.id: row for row in rows}
        return [
            ClaimHit(
                claim_id=item.key,
                text=by_id[item.key].text,
                level=by_id[item.key].evidenceLevel,
                subject_type=by_id[item.key].subjectType,
                subject_id=by_id[item.key].subjectId,
                **_ranking_fields(item),
            )
            for item in fused
        ]

    async def _chunk_hits(self, fused: Sequence[FusedItem[uuid.UUID]]) -> list[ChunkHit]:
        if not fused:
            return []
        columns = (
            Chunk.id,
            Chunk.sourceId,
            Chunk.ordinal,
            Chunk.locator,
            Chunk.text,
            Source.kind,
            Source.title,
        )
        rows = await self._session.execute(
            select(*columns)
            .join(Source, Source.id == Chunk.sourceId)
            .where(Chunk.id.in_([item.key for item in fused]))
        )
        by_id = {row.id: row for row in rows}
        return [
            ChunkHit(
                chunk_id=item.key,
                source_id=by_id[item.key].sourceId,
                ordinal=by_id[item.key].ordinal,
                locator=by_id[item.key].locator,
                text=by_id[item.key].text,
                source_kind=by_id[item.key].kind,
                source_title=by_id[item.key].title,
                **_ranking_fields(item),
            )
            for item in fused
        ]


async def search_words(text: str, english: EnglishRendering | None) -> str:
    if english is None or or_tsquery(text) is not None:
        return text
    return await english(text)


async def craft_scope(session: AsyncSession, slug: str | None) -> CraftScope:
    if slug is None:
        return EVERY_CRAFT
    row = (
        await session.execute(
            select(Craft.id, Craft.subCategoryId, CraftSubCategory.categoryId)
            .outerjoin(CraftSubCategory, CraftSubCategory.id == Craft.subCategoryId)
            .where(Craft.slug == slug)
        )
    ).first()
    if row is None:
        raise InvalidInput(f"No craft has the slug {slug!r}")
    return CraftScope(
        craft_id=row.id,
        sub_category_id=row.subCategoryId,
        category_id=row.categoryId,
        merged_ids=await merged_into(session, row.id),
    )


async def merged_into(session: AsyncSession, craft_id: uuid.UUID) -> tuple[uuid.UUID, ...]:
    found: list[uuid.UUID] = []
    reached = [craft_id]
    for _ in range(MERGE_HOPS_MAX):
        rows = await session.scalars(
            select(Craft.id)
            .where(Craft.mergedIntoId.in_(reached), Craft.id.not_in([craft_id, *found]))
            .order_by(Craft.id)
        )
        reached = list(rows.all())
        if not reached:
            break
        found += reached
    return tuple(found)


def _claim_conditions(query: KnowledgeQuery, scope: CraftScope) -> list[ColumnElement[bool]]:
    conditions = claim_conditions(scope, mode=query.mode, facets=query.facets, fields=query.fields)
    return [*conditions, cited_from_kinds(query.source_kinds)] if query.source_kinds else conditions


def _ranking_fields(item: FusedItem[uuid.UUID]) -> dict[str, float | int | None]:
    ranks = dict(zip(RANK_FIELDS, item.ranks, strict=False))
    return {"score": round(item.score, SCORE_DIGITS), **ranks}
