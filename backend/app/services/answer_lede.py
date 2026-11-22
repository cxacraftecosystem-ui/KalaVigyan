from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable, Mapping, Sequence
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from dataclasses import dataclass, field, replace
from functools import partial
from typing import Any, Protocol

from app.core.errors import AppError
from app.research.blocks_lede import LedeBlock
from app.research.composition import ComposedLede, LedeRequest
from app.research.crafts import CraftRef
from app.research.depth import depth_policy
from app.research.reading_style import ReadingStyle
from app.research.retrieval import KnowledgeRetriever
from app.research.sections import SectionSpec
from app.research.understanding import Understanding
from app.research.vocabulary import CANONICAL_LANGUAGE

from .answer_events import CitedClaims, joined_claims
from .answer_translation import AnswerTranslation, translated_block
from .claim_ledger import sentence_keys
from .explainer_events import ExplainerStream
from .lede_evidence import (
    CitedOf,
    LedeAsk,
    SearchedEvidence,
    SectionToHead,
    lede_query,
    lede_request,
    searched_evidence,
)
from .piece_lookup import PieceLookup, ReusedSection
from .section_blocks import BlockRefused, KeptSentence, lede_block
from .section_context import SectionOutcome
from .section_enrichment import Enrichment
from .signature_blocks import FiguredLede, SignatureFigures

__all__ = [
    "LEDE_WAIT_SECONDS",
    "AnswerOpening",
    "LedePlan",
    "LedeTools",
    "LedeWriting",
    "Opening",
    "OpeningStore",
    "SectionsShown",
    "early_opening",
    "late_opening",
    "lede_plan",
    "opening_lede",
    "sections_shown",
    "written_opening",
]

logger = logging.getLogger(__name__)

LEDE_WAIT_SECONDS = 30.0

ComposeLede = Callable[[LedeRequest], Awaitable[ComposedLede]]


class OpeningStore(Protocol):
    async def cited(self, claim_ids: Iterable[uuid.UUID]) -> CitedClaims: ...


@dataclass(frozen=True)
class LedeTools:
    compose: ComposeLede | None = None
    wait_seconds: float = LEDE_WAIT_SECONDS
    figures: SignatureFigures | None = None
    retriever: KnowledgeRetriever | None = None


@dataclass(frozen=True)
class LedePlan:
    question: str
    craft: CraftRef | None
    mode: str
    english: str
    heads: tuple[SectionToHead, ...] = ()
    reused: CitedClaims = field(default_factory=CitedClaims)
    style: ReadingStyle | None = None


@dataclass(frozen=True)
class Opening:
    lede: LedeBlock | None = None
    headings: Mapping[str, str] = field(default_factory=dict)
    follow_ups: tuple[str, ...] = ()
    sources: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    english: str = ""
    deferred: bool = False

    def asked(self, question: str) -> tuple[str, ...]:
        return tuple(dict.fromkeys(form for form in (question, self.english) if form))


@dataclass(frozen=True)
class SectionsShown:
    claim_ids: tuple[uuid.UUID, ...] = ()
    said: frozenset[str] = frozenset()


@dataclass(frozen=True)
class LedeWriting:
    stream: ExplainerStream
    translation: AnswerTranslation
    enrichment: Enrichment


@dataclass(frozen=True)
class AnswerOpening:
    plan: LedePlan
    tools: LedeTools
    writing: LedeWriting
    store: OpeningStore

    def started(self) -> AbstractAsyncContextManager[asyncio.Task[Opening]]:
        written = partial(early_opening, self.plan, self.tools, self.writing, self.store.cited)
        return opening_lede(self.writing.stream, written, wait_seconds=self.tools.wait_seconds)

    async def settled(self, first: Opening, outcomes: Sequence[SectionOutcome]) -> Opening:
        if first.lede is not None or not first.deferred:
            return first
        shown = sections_shown(outcomes)
        written = partial(late_opening, self.plan, self.tools, self.writing, self.store.cited, shown)
        late = await _softly(written, self.tools.wait_seconds)
        return late if late.lede is not None else first


@asynccontextmanager
async def opening_lede(
    stream: ExplainerStream,
    written: Callable[[], Awaitable[Opening]],
    *,
    wait_seconds: float = LEDE_WAIT_SECONDS,
) -> AsyncIterator[asyncio.Task[Opening]]:
    stream.hold_blocks_for_lede()
    task = asyncio.create_task(_sent_first(stream, written, wait_seconds))
    try:
        yield task
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        stream.release_blocks()


def lede_plan(
    question: str,
    understanding: Understanding,
    untitled: Sequence[SectionSpec],
    lookup: PieceLookup,
    *,
    style: ReadingStyle | None = None,
) -> LedePlan:
    reused = [(spec, lookup.reused[spec.discipline]) for spec in untitled if spec.discipline in lookup.reused]
    heads = tuple(
        SectionToHead(spec.id, spec.discipline, _claims_in_reading_order(section)) for spec, section in reused
    )
    mode = depth_policy(understanding.depth).mode
    cited = joined_claims(*(section.cited for _, section in reused))
    english = understanding.english_question or question
    return LedePlan(question, understanding.craft, mode, english, heads, cited, style=style)


async def early_opening(plan: LedePlan, tools: LedeTools, writing: LedeWriting, cited: CitedOf) -> Opening:
    if tools.compose is None:
        return Opening()
    found = await _searched(plan, tools, cited)
    evidence = joined_claims(found.cited, plan.reused)
    ask = LedeAsk(
        plan.question, plan.english, plan.craft, evidence, plan.heads, style=plan.style, ranked=found.ranked
    )
    return await written_opening(ask, tools, writing)


async def _searched(plan: LedePlan, tools: LedeTools, cited: CitedOf) -> SearchedEvidence:
    if plan.craft is None or tools.retriever is None:
        return SearchedEvidence()
    query = lede_query(plan.craft.slug, plan.english, plan.mode)
    return await searched_evidence(tools.retriever, cited, query)


async def late_opening(
    plan: LedePlan, tools: LedeTools, writing: LedeWriting, cited: CitedOf, shown: SectionsShown
) -> Opening:
    if tools.compose is None or not shown.claim_ids:
        return Opening()
    evidence = await cited(shown.claim_ids)
    ask = LedeAsk(plan.question, plan.english, plan.craft, evidence, said=shown.said, style=plan.style)
    opening = await written_opening(ask, tools, writing)
    if opening.lede is not None:
        await writing.stream.lede(opening.lede, opening.sources)
    return opening


async def written_opening(ask: LedeAsk, tools: LedeTools, writing: LedeWriting) -> Opening:
    if tools.compose is None:
        return Opening(english=ask.english)
    request = lede_request(ask)
    if not request.candidates:
        return Opening(english=ask.english, deferred=True)
    try:
        composed = await tools.compose(request)
    except AppError as error:
        logger.warning("the lede was not written: %s", error)
        return Opening(english=ask.english)
    shown = await _shown_lede(ask, composed, writing, tools.figures)
    return Opening(
        lede=shown.lede if shown is not None else None,
        headings=dict(composed.headings),
        follow_ups=tuple(composed.follow_ups),
        sources={**ask.evidence.sources, **(shown.sources if shown is not None else {})},
        english=ask.english,
    )


def sections_shown(outcomes: Sequence[SectionOutcome]) -> SectionsShown:
    sentences = [s for outcome in outcomes for block in outcome.blocks for s in block.cited_sentences()]
    return SectionsShown(
        claim_ids=tuple(dict.fromkeys(claim for outcome in outcomes for claim in outcome.claim_ids)),
        said=frozenset(key for s in sentences for key in sentence_keys(s.text, s.original)),
    )


async def _sent_first(
    stream: ExplainerStream, written: Callable[[], Awaitable[Opening]], wait_seconds: float
) -> Opening:
    try:
        opening = await _softly(written, wait_seconds)
        if opening.lede is not None:
            await stream.lede(opening.lede, opening.sources)
        return opening
    finally:
        stream.release_blocks()


async def _softly(written: Callable[[], Awaitable[Opening]], wait_seconds: float) -> Opening:
    try:
        async with asyncio.timeout(wait_seconds):
            return await written()
    except asyncio.CancelledError:
        raise
    except TimeoutError:
        logger.warning("the lede took longer than %s s; the answer opens with its sections", wait_seconds)
        return Opening()
    except Exception:
        logger.warning("the lede failed; the answer opens with its sections", exc_info=True)
        return Opening()


def _unsaid(ask: LedeAsk, composed: ComposedLede) -> list[KeptSentence] | None:
    sentences = [
        KeptSentence(
            s.text, tuple(s.claim_ids), tuple(s.evidence_ids), False, quotes=tuple(q.text for q in s.spans)
        )
        for s in composed.sentences
    ]
    if sentences and sentence_keys(sentences[0].text) & ask.said:
        logger.warning("the lede's answer sentence is already said by a section, so no lede is shown")
        return None
    return [s for n, s in enumerate(sentences) if n == 0 or not sentence_keys(s.text) & ask.said]


async def _shown_lede(
    ask: LedeAsk, composed: ComposedLede, writing: LedeWriting, figures: SignatureFigures | None
) -> FiguredLede | None:
    kept = _unsaid(ask, composed)
    if kept is None:
        return None
    try:
        lede = lede_block(ask.question, kept, ask.evidence)
    except BlockRefused as refused:
        logger.warning("%s", refused)
        return None
    figured = await _figured(ask, writing.enrichment.marked(lede), writing, figures)
    if writing.stream.language == CANONICAL_LANGUAGE:
        return figured
    await writing.stream.status("TRANSLATING")
    texts = {claim_id: view.text for claim_id, view in ask.evidence.views.items()}
    payload = figured.lede.model_dump(mode="json", by_alias=True)
    shown = await translated_block(
        payload, language=writing.stream.language, translation=writing.translation, claim_texts=texts
    )
    return replace(figured, lede=LedeBlock.model_validate(shown))


async def _figured(
    ask: LedeAsk, lede: LedeBlock, writing: LedeWriting, figures: SignatureFigures | None
) -> FiguredLede:
    if figures is None:
        return FiguredLede(lede)
    return await figures.figured(
        lede, question=ask.english, craft=ask.craft, evidence=ask.evidence, enrichment=writing.enrichment
    )


def _claims_in_reading_order(section: ReusedSection) -> tuple[uuid.UUID, ...]:
    cited = (citation.claim_id for piece in section.pieces for citation in piece.payload.citations())
    return tuple(uuid.UUID(claim) for claim in dict.fromkeys(cited))
