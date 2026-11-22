from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass

from app.research.composition import ComposeCandidate, ComposeFocus, ComposeRequest
from app.research.evidence import SourceDocument
from app.research.evidence_pack import EvidencePack
from app.research.field_voices import FIELD_SOURCE_KIND, FIELD_VOICES_ADAPTER
from app.research.quotes import trivial_quote
from app.research.reading_style import ReadingStyle
from app.research.research_summary import ResearchSummary, SearchedQuery
from app.research.retrieval import ChunkHit, ClaimHit
from app.research.vocabulary import LABEL_LEVELS

from .passages import best_passages, passage_terms

__all__ = [
    "EVIDENCE_LEVEL",
    "STORED_PASSAGES_ADAPTER",
    "WHOLE_TEXT_MAX_CHARS",
    "ClaimSupport",
    "claim_candidate",
    "compose_request",
    "document_candidate",
    "field_candidate",
    "field_evidence_id",
    "offered_passages",
    "passage_candidates",
    "research_summary",
    "stored_claim_candidate",
    "stored_passage_candidate",
    "stored_passage_id",
]

WHOLE_TEXT_MAX_CHARS = 4000
EVIDENCE_LEVEL = LABEL_LEVELS["QUOTED"]
LABEL_MAX_CHARS = 300
STORED_PASSAGES_ADAPTER = "stored_passages"


@dataclass(frozen=True)
class ClaimSupport:
    quotes: tuple[str, ...] = ()
    sources: tuple[str, ...] = ()


def compose_request(
    pack: EvidencePack,
    question: str,
    *,
    focus: ComposeFocus | None = None,
    style: ReadingStyle | None = None,
    support: Mapping[uuid.UUID, ClaimSupport] | None = None,
) -> ComposeRequest:
    backing = support or {}
    claims = [claim_candidate(hit, backing.get(hit.claim_id)) for hit in pack.stored.claims]
    passages = passage_candidates(pack.stored.chunks)
    terms = passage_terms(pack.plan)
    documents = [
        candidate for doc in pack.documents if (candidate := document_candidate(doc, terms)) is not None
    ]
    return ComposeRequest(
        question=question,
        craft=pack.plan.craft,
        candidates=[*claims, *passages, *documents],
        searched=research_summary(pack),
        focus=focus,
        style=style,
    )


def claim_candidate(hit: ClaimHit, support: ClaimSupport | None = None) -> ComposeCandidate:
    return stored_claim_candidate(hit.claim_id, hit.text, hit.level, support=support)


def stored_claim_candidate(
    claim_id: uuid.UUID, text: str, level: str, *, support: ClaimSupport | None = None
) -> ComposeCandidate:
    backing = support or ClaimSupport()
    label = "; ".join([f"stored claim, {level.lower()}", *backing.sources])
    return ComposeCandidate(
        id=str(claim_id),
        kind="CLAIM",
        text=text,
        quotes=[quote for quote in dict.fromkeys(backing.quotes) if quote and quote != text],
        source_label=label[:LABEL_MAX_CHARS],
        level=level,
    )


def offered_passages(hits: Iterable[ChunkHit]) -> list[ChunkHit]:
    return [hit for hit in hits if not trivial_quote(hit.text)]


def passage_candidates(hits: Iterable[ChunkHit]) -> list[ComposeCandidate]:
    return [
        field_candidate(hit) if hit.source_kind == FIELD_SOURCE_KIND else stored_passage_candidate(hit)
        for hit in offered_passages(hits)
    ]


def field_evidence_id(hit: ChunkHit) -> str:
    return f"{FIELD_VOICES_ADAPTER}:{hit.chunk_id}"


def stored_passage_id(hit: ChunkHit) -> str:
    return f"{STORED_PASSAGES_ADAPTER}:{hit.chunk_id}"


def field_candidate(hit: ChunkHit) -> ComposeCandidate:
    label = (
        f"field interview: {hit.source_title or 'a recorded interview'}, {hit.locator or 'whole recording'}"
    )
    return ComposeCandidate(
        id=field_evidence_id(hit),
        kind="EVIDENCE",
        text=hit.text,
        source_label=label[:LABEL_MAX_CHARS],
        level=EVIDENCE_LEVEL,
    )


def stored_passage_candidate(hit: ChunkHit) -> ComposeCandidate:
    where = hit.locator or f"passage {hit.ordinal + 1}"
    label = f"stored passage: {hit.source_title or 'a stored source'}, {where}"
    return ComposeCandidate(
        id=stored_passage_id(hit),
        kind="EVIDENCE",
        text=hit.text,
        source_label=label[:LABEL_MAX_CHARS],
        level=EVIDENCE_LEVEL,
    )


def document_candidate(
    document: SourceDocument, terms: frozenset[str] = frozenset()
) -> ComposeCandidate | None:
    passages = _passages(document, terms)
    if not passages:
        return None
    return ComposeCandidate(
        id=document.item.id,
        kind="EVIDENCE",
        text=passages[0],
        quotes=passages[1:],
        source_label=_source_label(document),
        level=EVIDENCE_LEVEL,
    )


def research_summary(pack: EvidencePack, *more: EvidencePack) -> ResearchSummary:
    packs = (pack, *more)
    found_by = {name for each in packs for entry in each.evidence for name in entry.found_by}
    failed = {failure.service for each in packs for failure in each.failures}
    asked = {name for each in packs for name in each.searched}
    queries = (SearchedQuery(tier=q.tier, text=q.query.text) for each in packs for q in each.plan.queries)
    return ResearchSummary(
        craft=pack.plan.craft,
        mode=pack.plan.mode,
        stored_claims=len({hit.claim_id for each in packs for hit in each.stored.claims}),
        stored_passages=len({hit.chunk_id for each in packs for hit in each.stored.chunks}),
        queries=tuple(dict.fromkeys(queries)),
        services=tuple(sorted(found_by | failed | asked)),
        evidence_found=len({entry.item.id for each in packs for entry in each.evidence}),
        documents_read=len({document.item.id for each in packs for document in each.documents}),
        failures=sum(len(each.failures) for each in packs),
    )


def _passages(document: SourceDocument, terms: frozenset[str]) -> list[str]:
    if len(document.text) <= WHOLE_TEXT_MAX_CHARS:
        return [document.text]
    quoted = list(dict.fromkeys(quote.text for quote in document.item.quotes))
    return quoted or best_passages(document.text, terms, budget=WHOLE_TEXT_MAX_CHARS)


def _source_label(document: SourceDocument) -> str:
    item = document.item
    year = item.published[:4] if item.published else "undated"
    where = item.publisher or item.adapter
    label = f"{item.title} ({where}, {year}, {document.content.lower().replace('_', ' ')})"
    return label[:LABEL_MAX_CHARS]
