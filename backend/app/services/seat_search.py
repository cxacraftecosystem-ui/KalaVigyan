from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable, Collection, Mapping, Sequence
from dataclasses import dataclass, field

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import InvalidInput
from app.planner.policy import SEAT_RESEARCH_DEPTHS, SEAT_RESEARCH_SECONDS, seat_gap_field
from app.research.coverage import FieldCoverage
from app.research.crafts import QUESTION_MAX_CHARS
from app.research.expert_panel import SeatBrief
from app.research.retrieval import OPEN_CHUNK_ACLS, KnowledgeHits, KnowledgeQuery
from app.research.vocabulary import FACT_LEVELS

from . import knowledge_view
from .answer_events import CitedClaims, cited_claims, joined_claims
from .builder_interface import BuildAsk, BuilderTools
from .coverage import craft_coverage
from .knowledge_view import ClaimView

__all__ = [
    "SEAT_CLAIMS_MAX",
    "SEAT_READING_ACLS",
    "SEAT_SEARCH_LIMIT",
    "SeatEvidence",
    "SeatSearch",
    "live_findings",
    "seat_findings",
    "seat_gaps",
    "seat_query",
    "stored_seat_search",
    "with_live",
]

logger = logging.getLogger(__name__)

SEAT_SEARCH_LIMIT = 12
SEAT_CLAIMS_MAX = 6
SEAT_READING_ACLS = OPEN_CHUNK_ACLS


@dataclass(frozen=True)
class SeatEvidence:
    found: Mapping[str, tuple[ClaimView, ...]] = field(default_factory=dict)
    cited: CitedClaims = field(default_factory=CitedClaims)


SeatSearch = Callable[[BuildAsk, Sequence[SeatBrief], Collection[str]], Awaitable[SeatEvidence]]


def seat_query(ask: BuildAsk, brief: SeatBrief) -> KnowledgeQuery:
    craft = ask.request.craft
    words = [ask.request.english_question or ask.request.question, craft.name if craft else ""]
    return KnowledgeQuery(
        craft_slug=craft.slug if craft else None,
        text=" ".join(word for word in words if word)[:QUESTION_MAX_CHARS],
        mode=ask.request.mode,
        fields=brief.fields,
        source_kinds=brief.source_kinds,
        passages=False,
        limit=SEAT_SEARCH_LIMIT,
        rerank=True,
    )


def seat_findings(
    briefs: Sequence[SeatBrief], hits: Sequence[KnowledgeHits], cited: CitedClaims, shown: Collection[str]
) -> dict[str, tuple[ClaimView, ...]]:
    return {brief.seat: _found(brief, found, cited, shown) for brief, found in zip(briefs, hits, strict=True)}


def stored_seat_search(tools: BuilderTools) -> SeatSearch:
    async def search(ask: BuildAsk, briefs: Sequence[SeatBrief], shown: Collection[str]) -> SeatEvidence:
        retriever = tools.retriever
        if retriever is None or tools.sessions is None or not briefs:
            return SeatEvidence()
        gaps = await seat_gaps(tools.sessions, ask, briefs)
        hits, live = await asyncio.gather(
            asyncio.gather(*(retriever.search(seat_query(ask, brief)) for brief in briefs)),
            live_findings(ask, gaps),
        )
        wanted = [hit.claim_id for found in hits for hit in found.claims]
        async with tools.sessions() as session:
            views, sources = await knowledge_view.claims_by_id(session, wanted, acls=SEAT_READING_ACLS)
        cited = joined_claims(cited_claims(list(views.values()), sources), *live.values())
        found = seat_findings(briefs, hits, cited, shown)
        return SeatEvidence(with_live(found, live, shown), cited)

    return search


async def seat_gaps(
    sessions: async_sessionmaker[AsyncSession], ask: BuildAsk, briefs: Sequence[SeatBrief]
) -> dict[str, tuple[SeatBrief, str]]:
    craft = ask.request.craft
    if ask.research is None or craft is None or ask.request.depth not in SEAT_RESEARCH_DEPTHS:
        return {}
    async with sessions() as session:
        coverage = await _coverage(session, craft.slug)
    gaps = {brief.seat: (brief, seat_gap_field(brief, coverage)) for brief in briefs}
    return {seat: (brief, gap) for seat, (brief, gap) in gaps.items() if gap is not None}


async def live_findings(ask: BuildAsk, gaps: Mapping[str, tuple[SeatBrief, str]]) -> dict[str, CitedClaims]:
    research = ask.research
    if research is None or not gaps:
        return {}
    results = await asyncio.gather(
        *(asyncio.wait_for(research(brief, gap), SEAT_RESEARCH_SECONDS) for brief, gap in gaps.values()),
        return_exceptions=True,
    )
    found: dict[str, CitedClaims] = {}
    for seat, result in zip(gaps, results, strict=True):
        if isinstance(result, CitedClaims):
            found[seat] = result
        elif isinstance(result, Exception):
            logger.warning("the %s seat of %s stays on stored evidence: %s", seat, ask.section.id, result)
        else:
            raise result
    return found


def with_live(
    found: Mapping[str, tuple[ClaimView, ...]], live: Mapping[str, CitedClaims], shown: Collection[str]
) -> dict[str, tuple[ClaimView, ...]]:
    merged = dict(found)
    for seat, cited in live.items():
        own = [
            view for view in cited.views.values() if str(view.id) not in shown and view.level in FACT_LEVELS
        ]
        mine = {view.id for view in own}
        rest = [view for view in found.get(seat, ()) if view.id not in mine]
        merged[seat] = tuple([*own, *rest][:SEAT_CLAIMS_MAX])
    return merged


async def _coverage(session: AsyncSession, slug: str) -> FieldCoverage | None:
    try:
        return await craft_coverage(session, slug)
    except InvalidInput:
        return None


def _found(
    brief: SeatBrief, hits: KnowledgeHits, cited: CitedClaims, shown: Collection[str]
) -> tuple[ClaimView, ...]:
    kinds = set(brief.source_kinds)
    kept: dict[uuid.UUID, ClaimView] = {}
    for hit in hits.claims:
        view = cited.views.get(hit.claim_id)
        if view is None or view.id in kept or str(view.id) in shown or view.level not in FACT_LEVELS:
            continue
        if _source_kinds(view, cited) & kinds:
            kept[view.id] = view
        if len(kept) == SEAT_CLAIMS_MAX:
            break
    return tuple(kept.values())


def _source_kinds(view: ClaimView, cited: CitedClaims) -> set[str]:
    refs = (cited.sources.get(str(citation["sourceId"])) for citation in view.citations)
    return {str(ref["kind"]) for ref in refs if ref is not None and ref.get("kind")}
