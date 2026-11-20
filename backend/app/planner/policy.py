from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from app.research.coverage import FieldCoverage
from app.research.depth import depth_policy, research_budget
from app.research.evidence import SEARCH_MAX_K
from app.research.expert_panel import EXPERT_PANEL, WIDENED_DEPTHS, SeatBrief, speaking_seats
from app.research.planning import MODE_POLICIES, PlanRequest, ResearchShare
from app.research.vocabulary import CANONICAL_LANGUAGE
from app.sources.reference.wikidata import WikidataAdapter
from app.sources.reference.wikipedia import WIKIPEDIA_LANGUAGES, WikipediaAdapter

__all__ = [
    "COVERAGE_QUERY_LIMIT",
    "DEEP_REFERENCE_RESERVE",
    "DEGRADED_MODES",
    "DOCUMENT_TIMEOUT_SECONDS",
    "LIVE_BUDGETS",
    "NATIVE_QUERY_SEARCHERS",
    "PLAN_DRAFT_RETRIES",
    "READ_ATTEMPT_FACTOR",
    "READ_CONCURRENCY",
    "REFERENCES_PER_DOCUMENT",
    "SEARCH_CONCURRENCY",
    "SEARCH_TIMEOUT_SECONDS",
    "SEAT_LIVE_SHARE",
    "SEAT_RESEARCH_DEPTHS",
    "SEAT_RESEARCH_SECONDS",
    "SEAT_SENTENCES_MAX",
    "STORED_PACK_LIMIT",
    "TierBudget",
    "native_query_limit",
    "reference_reserve",
    "request_limits",
    "seat_gap_field",
    "seat_reading_kinds",
    "stored_pack_limit",
]

PLAN_DRAFT_RETRIES = 1
COVERAGE_QUERY_LIMIT = 10
STORED_PACK_LIMIT = 20
SEARCH_CONCURRENCY = 12
SEARCH_TIMEOUT_SECONDS = 30.0
READ_CONCURRENCY = 8
DOCUMENT_TIMEOUT_SECONDS = 45.0
READ_ATTEMPT_FACTOR = 2
DEEP_REFERENCE_RESERVE = 15
REFERENCES_PER_DOCUMENT = 5
DEGRADED_MODES: Mapping[str, str] = MappingProxyType({"DEEP": "HYBRID"})
NATIVE_QUERY_SEARCHERS = frozenset({WikipediaAdapter.name, WikidataAdapter.name})
SEAT_LIVE_SHARE = ResearchShare(queries=1, native_queries=0, fetches=1)
SEAT_RESEARCH_DEPTHS = WIDENED_DEPTHS
SEAT_RESEARCH_SECONDS = 50.0
SEAT_SENTENCES_MAX = 3


@dataclass(frozen=True)
class TierBudget:
    results_per_source: int
    open_access: bool
    follows_references: bool

    def __post_init__(self) -> None:
        if not 1 <= self.results_per_source <= SEARCH_MAX_K:
            raise ValueError(f"results_per_source is 1 to {SEARCH_MAX_K}")


LIVE_BUDGETS: Mapping[str, Mapping[str, TierBudget]] = MappingProxyType(
    {
        "HYBRID": MappingProxyType(
            {
                "T3": TierBudget(results_per_source=5, open_access=False, follows_references=False),
                "T4": TierBudget(results_per_source=8, open_access=False, follows_references=False),
            }
        ),
        "DEEP": MappingProxyType(
            {
                "T3": TierBudget(results_per_source=10, open_access=True, follows_references=True),
                "T4": TierBudget(results_per_source=15, open_access=False, follows_references=True),
            }
        ),
    }
)


def native_query_limit(language: str, mode: str) -> int:
    if language == CANONICAL_LANGUAGE or language not in WIKIPEDIA_LANGUAGES:
        return 0
    return MODE_POLICIES[mode].max_native_queries


def reference_reserve(max_fetches: int) -> int:
    return max_fetches * DEEP_REFERENCE_RESERVE // MODE_POLICIES["DEEP"].max_fetches


def seat_gap_field(brief: SeatBrief, coverage: FieldCoverage | None) -> str | None:
    if coverage is None:
        return None
    own = brief.fields[0]
    return None if own in coverage.covered else own


def seat_reading_kinds(request: PlanRequest) -> tuple[tuple[str, ...], ...]:
    seats = speaking_seats(request.focus, request.seats, depth=request.depth)
    return tuple(EXPERT_PANEL[seat].source_kinds for seat in seats)


def request_limits(request: PlanRequest, mode: str) -> ResearchShare:
    budget = research_budget(mode, request.depth)
    limits = ResearchShare(
        queries=budget.max_queries,
        native_queries=native_query_limit(request.language, mode),
        fetches=budget.max_fetches,
    )
    return limits if request.share is None else request.share.capped(limits)


def stored_pack_limit(depth: str | None) -> int:
    return STORED_PACK_LIMIT if depth is None else depth_policy(depth).stored_claims
