from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field

from app.research.composition import ComposeCandidate, LedeRequest, LedeSection
from app.research.crafts import QUESTION_MAX_CHARS, CraftRef
from app.research.planning import OPEN_QUESTION_LEVEL
from app.research.reading_style import ReadingStyle
from app.research.retrieval import KnowledgeQuery, KnowledgeRetriever
from app.research.vocabulary import LEVEL_ORDER

from .answer_events import CitedClaims
from .knowledge_view import ClaimView

__all__ = [
    "HEADING_CLAIMS_MAX",
    "LEDE_CLAIMS_MAX",
    "LEDE_SEARCH_LIMIT",
    "CitedOf",
    "LedeAsk",
    "SearchedEvidence",
    "SectionToHead",
    "lede_query",
    "lede_request",
    "offered_views",
    "searched_evidence",
]

LEDE_SEARCH_LIMIT = 24
LEDE_CLAIMS_MAX = 16
HEADING_CLAIMS_MAX = 8
LABEL_MAX_CHARS = 300

CitedOf = Callable[[Iterable[uuid.UUID]], Awaitable[CitedClaims]]


@dataclass(frozen=True)
class SectionToHead:
    section_id: str
    discipline: str
    claim_ids: tuple[uuid.UUID, ...]


@dataclass(frozen=True)
class SearchedEvidence:
    cited: CitedClaims = field(default_factory=CitedClaims)
    ranked: tuple[uuid.UUID, ...] = ()


@dataclass(frozen=True)
class LedeAsk:
    question: str
    english: str
    craft: CraftRef | None
    evidence: CitedClaims
    sections: tuple[SectionToHead, ...] = ()
    said: frozenset[str] = frozenset()
    style: ReadingStyle | None = None
    ranked: tuple[uuid.UUID, ...] = ()


def lede_query(craft_slug: str, english: str, mode: str) -> KnowledgeQuery:
    return KnowledgeQuery(
        craft_slug=craft_slug, text=english[:QUESTION_MAX_CHARS], mode=mode, limit=LEDE_SEARCH_LIMIT
    )


async def searched_evidence(
    retriever: KnowledgeRetriever, cited: CitedOf, query: KnowledgeQuery
) -> SearchedEvidence:
    hits = await retriever.search(query)
    ranked = tuple(dict.fromkeys(hit.claim_id for hit in hits.claims))
    if not ranked:
        return SearchedEvidence()
    return SearchedEvidence(await cited(ranked), ranked)


def lede_request(ask: LedeAsk) -> LedeRequest:
    views = offered_views(ask)
    shown = {view.id for view in views}
    sections = [
        LedeSection(
            section_id=section.section_id,
            discipline=section.discipline,
            claim_ids=[str(claim) for claim in section.claim_ids if claim in shown],
        )
        for section in ask.sections
        if any(claim in shown for claim in section.claim_ids)
    ]
    return LedeRequest(
        question=ask.english,
        craft=ask.craft,
        candidates=[_candidate(view) for view in views],
        sections=sections,
        style=ask.style,
    )


def offered_views(ask: LedeAsk) -> list[ClaimView]:
    facts = {
        claim_id: view for claim_id, view in ask.evidence.views.items() if view.level != OPEN_QUESTION_LEVEL
    }
    searched = [facts[claim] for claim in ask.ranked if claim in facts]
    found = {view.id for view in searched}
    rest = sorted(
        (view for claim, view in facts.items() if claim not in found),
        key=lambda view: LEVEL_ORDER.get(view.level, 9),
    )
    heading_claims = [
        claim
        for section in ask.sections
        for claim in section.claim_ids[:HEADING_CLAIMS_MAX]
        if claim in facts
    ]
    chosen = dict.fromkeys([*(view.id for view in [*searched, *rest][:LEDE_CLAIMS_MAX]), *heading_claims])
    return [facts[claim_id] for claim_id in chosen]


def _candidate(view: ClaimView) -> ComposeCandidate:
    quotes = list(dict.fromkeys(c["quote"] for c in view.citations if c.get("quote")))
    return ComposeCandidate(
        id=str(view.id),
        kind="CLAIM",
        text=view.text,
        quotes=quotes,
        source_label=f"stored claim, {view.level.lower()}"[:LABEL_MAX_CHARS],
        level=view.level,
    )
