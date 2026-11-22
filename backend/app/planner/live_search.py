from __future__ import annotations

import asyncio
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.core.errors import ExternalFailure, NotConfigured
from app.models.enums import RELIABILITIES
from app.research.evidence import EvidenceItem, SourceAdapter
from app.research.evidence_pack import PackedEvidence
from app.research.planning import NATIVE_QUERY_TIER, PlannedQuery, RetrievalPlan
from app.research.vocabulary import CANONICAL_LANGUAGE

from .failures import FailureLog
from .policy import LIVE_BUDGETS, NATIVE_QUERY_SEARCHERS, SEARCH_CONCURRENCY, SEARCH_TIMEOUT_SECONDS

__all__ = [
    "LIVE_RESEARCH_SERVICE",
    "SEARCH_STAGE",
    "SearchHit",
    "asked_searchers",
    "merged_evidence",
    "run_searches",
]

LIVE_RESEARCH_SERVICE = "live_research"
SEARCH_STAGE = "SEARCH"
TRUST_ORDER = {tier: rank for rank, tier in enumerate(RELIABILITIES)}


@dataclass(frozen=True)
class SearchHit:
    searcher: str
    query_index: int
    rank: int
    item: EvidenceItem


async def run_searches(
    plan: RetrievalPlan, searchers: Sequence[SourceAdapter], log: FailureLog
) -> list[SearchHit]:
    gate = asyncio.Semaphore(SEARCH_CONCURRENCY)
    calls = [
        _search(gate, searcher, index, query, mode=plan.mode, log=log)
        for index, query, searcher in _routed(plan, searchers)
    ]
    if not calls:
        return []
    results = await asyncio.gather(*calls)
    if all(result is None for result in results):
        raise ExternalFailure(
            f"every live search failed ({log.count(SEARCH_STAGE)} searches)",
            kind="unavailable",
            retryable=True,
            service=LIVE_RESEARCH_SERVICE,
        )
    return [hit for result in results if result for hit in result]


def asked_searchers(plan: RetrievalPlan, searchers: Sequence[SourceAdapter]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(searcher.name for _, _, searcher in _routed(plan, searchers)))


def merged_evidence(plan: RetrievalPlan, hits: Sequence[SearchHit]) -> list[PackedEvidence]:
    groups: list[list[SearchHit]] = []
    by_key: dict[str, list[SearchHit]] = {}
    for hit in hits:
        group = by_key.get(hit.item.source_key) or by_key.get(f"id:{hit.item.id}")
        if group is None:
            group = []
            groups.append(group)
        group.append(hit)
        by_key[hit.item.source_key] = group
        by_key[f"id:{hit.item.id}"] = group
    packed = [_packed(plan, group) for group in groups]
    return sorted(packed, key=evidence_rank)


def evidence_rank(entry: PackedEvidence) -> tuple[int, int, int, str]:
    return (TRUST_ORDER[entry.item.trust], -entry.hits, entry.best_rank, entry.item.id)


def _packed(plan: RetrievalPlan, group: Sequence[SearchHit]) -> PackedEvidence:
    lead = min(group, key=lambda hit: (TRUST_ORDER[hit.item.trust], -len(hit.item.quotes), hit.rank))
    return PackedEvidence(
        item=lead.item,
        facet_indexes=tuple(sorted({plan.queries[hit.query_index].facet_index for hit in group})),
        found_by=tuple(dict.fromkeys([lead.searcher, *(hit.searcher for hit in group)])),
        hits=len({(hit.searcher, hit.query_index) for hit in group}),
        best_rank=min(hit.rank for hit in group),
    )


def _routed(
    plan: RetrievalPlan, searchers: Sequence[SourceAdapter]
) -> list[tuple[int, PlannedQuery, SourceAdapter]]:
    by_tier = _searchers_by_tier(plan, searchers)
    return [
        (index, query, searcher)
        for index, query in enumerate(plan.queries)
        for searcher in _query_searchers(query, by_tier)
    ]


def _searchers_by_tier(
    plan: RetrievalPlan, searchers: Sequence[SourceAdapter]
) -> Mapping[str, list[SourceAdapter]]:
    by_tier: dict[str, list[SourceAdapter]] = {}
    for searcher in searchers:
        by_tier.setdefault(searcher.tier, []).append(searcher)
    missing = sorted({query.tier for query in plan.queries} - by_tier.keys())
    if missing:
        raise NotConfigured("live sources", f"No live source can search tier {', '.join(missing)}")
    native = any(query.query.language != CANONICAL_LANGUAGE for query in plan.queries)
    if native and not any(s.name in NATIVE_QUERY_SEARCHERS for s in by_tier.get(NATIVE_QUERY_TIER, ())):
        raise NotConfigured("live sources", f"No live source can search in {plan.language}")
    return by_tier


def _query_searchers(query: PlannedQuery, by_tier: Mapping[str, list[SourceAdapter]]) -> list[SourceAdapter]:
    searchers = by_tier[query.tier]
    if query.query.language == CANONICAL_LANGUAGE:
        return searchers
    return [searcher for searcher in searchers if searcher.name in NATIVE_QUERY_SEARCHERS]


async def _search(
    gate: asyncio.Semaphore,
    searcher: SourceAdapter,
    index: int,
    query: PlannedQuery,
    *,
    mode: str,
    log: FailureLog,
) -> list[SearchHit] | None:
    k = LIVE_BUDGETS[mode][query.tier].results_per_source
    async with gate:
        items = await log.guarded(
            asyncio.wait_for(searcher.search(query.query, k), SEARCH_TIMEOUT_SECONDS),
            stage=SEARCH_STAGE,
            service=searcher.name,
            target=query.query.text,
        )
    if items is None:
        return None
    return [SearchHit(searcher.name, index, rank, item) for rank, item in enumerate(items[:k], start=1)]
