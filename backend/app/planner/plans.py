from __future__ import annotations

import logging
import re
from collections.abc import Sequence

from app.research.crafts import CraftRef
from app.research.evidence import SEARCH_QUERY_MAX_CHARS, SearchQuery, personal_data_in
from app.research.planning import (
    MODE_POLICIES,
    NATIVE_QUERY_TIER,
    FacetCoverage,
    PlannedQuery,
    PlanRequest,
    RetrievalPlan,
)
from app.research.vocabulary import CANONICAL_LANGUAGE, RETRIEVAL_TIERS, STORED_TIERS

from .colourants import colourant_queries
from .drafting import DraftQuery, PlanDraft
from .policy import DEGRADED_MODES, request_limits

__all__ = [
    "DEFAULT_QUERY_TIER",
    "effective_mode",
    "native_queries",
    "open_facets",
    "planned_queries",
    "retrieval_plan",
    "search_question",
]

logger = logging.getLogger(__name__)

DEFAULT_QUERY_TIER = "T3"
ANCHOR_MIN_CHARS = 3
WORD = re.compile(r"[^\W_]+")


def effective_mode(mode: str, *, degraded: bool) -> str:
    return DEGRADED_MODES.get(mode, mode) if degraded else mode


def open_facets(mode: str, coverage: Sequence[FacetCoverage], *, fresh: bool = False) -> list[int]:
    policy = MODE_POLICIES[mode]
    if not policy.max_queries:
        return []
    stored_first = policy.live_only_for_open_facets and not fresh
    return [entry.facet_index for entry in coverage if not (stored_first and entry.covered)]


def retrieval_plan(
    request: PlanRequest, draft: PlanDraft, coverage: Sequence[FacetCoverage], *, mode: str
) -> RetrievalPlan:
    policy = MODE_POLICIES[mode]
    limits = request_limits(request, mode)
    facets = open_facets(mode, coverage, fresh=request.fresh)
    native = native_queries(request, draft, facets, limit=limits.native_queries)
    queries = [*planned_queries(request, draft, facets, limit=limits.queries), *native]
    live_tiers = {query.tier for query in queries}
    return RetrievalPlan(
        mode=mode,
        craft=request.craft,
        intent=draft.intent,
        language=request.language,
        needs_region=draft.needs_region,
        facets=draft.facets,
        tiers=[
            tier
            for tier in RETRIEVAL_TIERS
            if tier in policy.tiers and (tier in STORED_TIERS or tier in live_tiers)
        ],
        queries=queries,
        max_fetches=limits.fetches if queries else 0,
    )


def planned_queries(
    request: PlanRequest, draft: PlanDraft, facet_indexes: Sequence[int], *, limit: int
) -> list[PlannedQuery]:
    wanted = set(facet_indexes)
    drafted = [query for query in draft.queries if query.facet_index in wanted]
    firsts = [_first_query(request.craft, draft, drafted, index) for index in facet_indexes]
    colourants = colourant_queries(search_question(request, draft), request.craft, draft, facet_indexes)
    ordered = [*firsts, *colourants, *(query for query in drafted if query not in firsts)]
    planned: list[PlannedQuery] = []
    seen: set[tuple[str, str]] = set()
    for query in ordered:
        search = search_query(query.text, request.craft, withheld=request.withheld_terms)
        key = (query.tier, search.text.casefold()) if search else None
        if search is None or key in seen:
            continue
        seen.add(key)
        planned.append(PlannedQuery(tier=query.tier, facet_index=query.facet_index, query=search))
    return planned[:limit]


def native_queries(
    request: PlanRequest, draft: PlanDraft, facet_indexes: Sequence[int], *, limit: int
) -> list[PlannedQuery]:
    wanted = set(facet_indexes)
    planned: list[PlannedQuery] = []
    seen: set[str] = set()
    for query in draft.native_queries if limit else ():
        if query.facet_index not in wanted:
            continue
        search = search_query(
            query.text,
            request.craft,
            withheld=request.withheld_terms,
            language=request.language,
            native_name=draft.native_craft_name,
        )
        if search is None or search.text.casefold() in seen:
            continue
        seen.add(search.text.casefold())
        planned.append(PlannedQuery(tier=NATIVE_QUERY_TIER, facet_index=query.facet_index, query=search))
    return planned[:limit]


def search_question(request: PlanRequest, draft: PlanDraft) -> str:
    return request.english_question or draft.english_question or request.question


def search_query(
    text: str,
    craft: CraftRef | None,
    *,
    withheld: Sequence[str],
    language: str = CANONICAL_LANGUAGE,
    native_name: str = "",
) -> SearchQuery | None:
    anchored = _anchored(text, craft, native_name)
    if personal_data_in(anchored):
        logger.warning("left out a planned query that carried personal data")
        return None
    if any(_mentions(anchored, term) for term in withheld):
        logger.warning("left out a planned query that named a withheld term")
        return None
    return SearchQuery(text=anchored, language=language)


def _first_query(
    craft: CraftRef | None, draft: PlanDraft, drafted: Sequence[DraftQuery], index: int
) -> DraftQuery:
    for query in drafted:
        if query.facet_index == index:
            return query
    target = draft.facets[index].target
    text = f"{craft.name} {target}" if craft else target
    return DraftQuery(facet_index=index, tier=DEFAULT_QUERY_TIER, text=text)


def _anchored(text: str, craft: CraftRef | None, native_name: str = "") -> str:
    if craft is None:
        return text[:SEARCH_QUERY_MAX_CHARS].strip()
    if _names(text, craft.name) or (native_name and _names_natively(text, native_name)):
        return text[:SEARCH_QUERY_MAX_CHARS].strip()
    return f"{native_name or craft.name} {text}"[:SEARCH_QUERY_MAX_CHARS].strip()


def _names(text: str, name: str) -> bool:
    words = {word.casefold() for word in WORD.findall(text)}
    anchors = {word.casefold() for word in WORD.findall(name) if len(word) >= ANCHOR_MIN_CHARS}
    return not anchors or bool(words & anchors)


def _names_natively(text: str, native_name: str) -> bool:
    folded = text.casefold()
    return any(part.casefold() in folded for part in native_name.split() if len(part) >= ANCHOR_MIN_CHARS)


def _mentions(text: str, term: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(term.casefold())}(?!\w)", text.casefold()) is not None
