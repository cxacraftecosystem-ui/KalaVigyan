from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field, replace
from functools import partial
from typing import Any, Protocol

from app.composer.candidates import compose_request, research_summary
from app.core.errors import AppError, spend_refusal
from app.research.blocks_component import stood_for
from app.research.composition import ComposedAnswer, ComposeFocus, ComposeRequest, searched_note
from app.research.depth import section_sentence_limit
from app.research.evidence_pack import EvidencePack, ResearchTrail
from app.research.explainer import Block
from app.research.planning import PlanRequest, ResearchShare, RetrievalPlan
from app.research.reading_style import ReadingStyle
from app.research.sections import DISCIPLINE_TITLES, LADDER_DISCIPLINE, SectionSpec, block_id
from app.research.stream import ResearchProgress
from app.science.ladder import ladder_problems, ladder_stage_options, process_ladder
from app.science.records import ProcessRecords

from .answer_catalogue import CatalogueLookup, SectionCatalogue, no_catalogue
from .answer_events import CitedClaims, joined_claims
from .answer_translation import AnswerTranslation
from .block_builders import AddedBlocks, BlockBuilders, SectionBuilds
from .claim_ledger import COVERED_NOTE
from .explainer_events import ExplainerStream
from .research_ledger import ResearchLedger, may_research_fresh
from .reuse_enrichment import Floor, claim_texts, floor_sent, process_sources
from .seat_research import BuildAsk, section_ask
from .section_blocks import (
    BlockRefused,
    KeptSentence,
    cited_sentence,
    kept_sentences,
    prose_block,
    section_sentences,
)
from .section_deepening import LADDER_KIND, NEW_SECTION, Deepening
from .section_enrichment import Enrichment, PictureSearches
from .section_headings import composed_heading
from .section_language import block_in_language, open_questions_in_language
from .section_trail import quote_trail, stored_sources

__all__ = [
    "SECTION_CONCURRENCY",
    "SECTION_STOPPED_NOTE",
    "SectionContext",
    "SectionOutcome",
    "SectionStore",
    "SectionTools",
    "run_sections",
]

logger = logging.getLogger(__name__)

SECTION_CONCURRENCY = 4
SECTION_STOPPED_NOTE = "Research for this section stopped before a source could be read."

ClaimsOf = tuple[tuple[uuid.UUID, ...], ...]


class SectionStore(Protocol):
    async def keep(self, answer_id: uuid.UUID, pack: EvidencePack, composed: ComposedAnswer) -> ClaimsOf: ...

    async def cited(self, claim_ids: Iterable[uuid.UUID]) -> CitedClaims: ...


@dataclass(frozen=True)
class SectionTools:
    research: Callable[[PlanRequest, ResearchProgress, ResearchTrail], Awaitable[EvidencePack]]
    compose: Callable[[ComposeRequest], Awaitable[ComposedAnswer]]
    store: SectionStore
    translation: AnswerTranslation
    catalogue: CatalogueLookup = no_catalogue


@dataclass(frozen=True)
class SectionContext:
    tools: SectionTools
    stream: ExplainerStream
    answer_id: uuid.UUID
    base: PlanRequest
    ledger: ResearchLedger
    enrichment: Enrichment
    process: ProcessRecords | None = None
    builders: BlockBuilders = field(default_factory=BlockBuilders)
    deepening: Mapping[str, Deepening] = field(default_factory=dict)
    floors: Mapping[str, Floor] = field(default_factory=dict)
    reading_style: ReadingStyle | None = None

    def deepening_of(self, section_id: str) -> Deepening:
        return self.deepening.get(section_id, NEW_SECTION)


@dataclass(frozen=True)
class SectionOutcome:
    spec: SectionSpec
    blocks: tuple[Block, ...] = ()
    built: tuple[Block, ...] = ()
    searched: str | None = None
    plans: tuple[RetrievalPlan, ...] = ()
    packs: tuple[EvidencePack, ...] = ()
    follow_ups: tuple[str, ...] = ()
    claim_ids: tuple[uuid.UUID, ...] = ()
    sources: Mapping[str, Mapping[str, Any]] = field(default_factory=dict)
    failure: AppError | None = None
    shown_title: str | None = None


@dataclass(frozen=True)
class _Attempt:
    pack: EvidencePack
    composed: ComposedAnswer
    blocks: tuple[Block, ...]
    open_questions: tuple[dict[str, Any], ...]
    cited: CitedClaims
    evidence_ids: tuple[str, ...]
    claim_ids: tuple[uuid.UUID, ...] = field(default=())
    floored: tuple[Block, ...] = ()


async def run_sections(specs: Sequence[SectionSpec], context: SectionContext) -> list[SectionOutcome]:
    gate = asyncio.Semaphore(SECTION_CONCURRENCY)
    try:
        async with asyncio.TaskGroup() as group:
            tasks = [
                group.create_task(_guarded(s, share, context, gate))
                for s, share in zip(specs, context.ledger.shares, strict=True)
            ]
    except BaseExceptionGroup as failed:
        raise _first_failure(failed) from None
    return [task.result() for task in tasks]


async def _guarded(
    spec: SectionSpec, share: ResearchShare, context: SectionContext, gate: asyncio.Semaphore
) -> SectionOutcome:
    floor = context.floors.get(spec.id, Floor())
    floored: tuple[Block, ...] = ()
    try:
        floored = await floor_sent(
            spec, floor, stream=context.stream, translation=context.tools.translation, process=context.process
        )
        async with gate:
            return await _section(spec, share, context, floor, floored)
    except AppError as error:
        if spend_refusal(error):
            raise
        logger.warning("section %s stopped: %s", spec.id, error, exc_info=True)
        searched = None if floored else SECTION_STOPPED_NOTE
        await context.stream.section_done(spec.id, searched=searched)
        claims = _claim_ids(floored, ())
        return SectionOutcome(spec, blocks=floored, searched=searched, failure=error, claim_ids=claims)


async def _section(
    spec: SectionSpec, share: ResearchShare, context: SectionContext, floor: Floor, floored: tuple[Block, ...]
) -> SectionOutcome:
    attempts = [await _attempt(spec, context, context.ledger.take_section(share), fresh=False)]
    fresh = context.ledger.take_fresh(share) if _needs_fresh(attempts[0], floored) else None
    if fresh is not None:
        await context.stream.section_state(spec.id, "RESEARCHING")
        attempts.append(await _attempt(spec, context, fresh, fresh=True))
    shown = replace(attempts[-1], floored=floored)
    proposed = None if spec.id in context.deepening and not floored else shown.composed.heading
    headed = await composed_heading(spec, shown, proposed, context.stream, context.tools.translation)
    cited = joined_claims(floor.cited, shown.cited)
    blocks, added = await _built_on(
        spec,
        shown,
        context,
        section_ask(context, spec, (*floor.placed.blocks, *shown.blocks), cited),
    )
    packs = tuple(attempt.pack for attempt in attempts)
    searched = _searched(blocks, shown, packs)
    sources = {**_section_sources(cited, context.process), **added.sources, **context.stream.shown_sources()}
    await context.stream.section_done(spec.id, searched=searched)
    await quote_trail(context.stream.trail, shown.evidence_ids, blocks, sources)
    return SectionOutcome(
        headed.spec,
        shown_title=headed.shown,
        blocks=blocks,
        built=(*floor.placed.built, *floor.placed.copies, *shown.blocks, *added.blocks),
        searched=searched,
        plans=tuple(pack.plan for pack in packs),
        packs=packs,
        follow_ups=tuple(shown.composed.follow_ups),
        claim_ids=tuple(
            dict.fromkeys([*_claim_ids(floored, ()), *shown.claim_ids, *_claim_ids(added.blocks, ())])
        ),
        sources=sources,
    )


async def _built_on(
    spec: SectionSpec, shown: _Attempt, context: SectionContext, ask: BuildAsk
) -> tuple[tuple[Block, ...], AddedBlocks]:
    shown_kinds = {*context.deepening_of(spec.id).kinds, *stood_for(shown.blocks)}
    async with (
        context.enrichment.searching() as pictures,
        context.builders.without(shown_kinds).building() as builds,
    ):
        builds.start(ask)
        return await _shown(spec, shown, context, pictures, builds)


async def _attempt(
    spec: SectionSpec, context: SectionContext, share: ResearchShare, *, fresh: bool
) -> _Attempt:
    pack = await _researched(spec, context, share, fresh=fresh)
    await context.stream.section_state(spec.id, "WRITING")
    offered = await context.tools.catalogue(context.base, spec.discipline)
    focus = _focus(spec, context, offered)
    request = compose_request(pack, context.base.question, focus=focus, style=context.reading_style)
    if request.candidates:
        await context.stream.status("COMPOSING", len(request.candidates))
    composed = await context.tools.compose(request)
    await context.stream.section_state(spec.id, "CHECKING")
    claims_of = await _kept(context, pack, composed)
    cited = await context.tools.store.cited(claim for claims in claims_of for claim in claims)
    sentences = context.deepening_of(spec.id).unshown(kept_sentences(composed, claims_of))
    return _built(spec, context, pack, composed, sentences=sentences, cited=cited, offered=offered)


async def _researched(
    spec: SectionSpec, context: SectionContext, share: ResearchShare, *, fresh: bool
) -> EvidencePack:
    request = PlanRequest.model_validate(
        context.base.model_dump() | {"focus": spec.discipline, "share": share.model_dump(), "fresh": fresh}
    )

    async def progress(step: Any, count: int) -> None:
        await context.stream.status(step, count)

    pack = await context.tools.research(request, progress, context.stream.trail)
    context.ledger.settle(share, pack)
    stored = await context.tools.store.cited(hit.claim_id for hit in pack.stored.claims)
    await context.stream.trail.found_stored(stored_sources(pack, stored))
    return pack


async def _kept(context: SectionContext, pack: EvidencePack, composed: ComposedAnswer) -> ClaimsOf:
    if composed.not_enough_evidence is not None and not pack.documents:
        return ()
    if pack.documents:
        await context.stream.status("WRITING_BACK", len(pack.documents))
    return await context.tools.store.keep(context.answer_id, pack, composed)


def _built(
    spec: SectionSpec,
    context: SectionContext,
    pack: EvidencePack,
    composed: ComposedAnswer,
    *,
    sentences: Sequence[KeptSentence],
    cited: CitedClaims,
    offered: SectionCatalogue,
) -> _Attempt:
    split = section_sentences(sentences, cited)
    deepening = context.deepening_of(spec.id)
    blocks: list[Block] = []
    ladder = None if deepening.shows(LADDER_KIND) else _ladder(spec, context, composed, deepening.number(1))
    if ladder is not None:
        blocks.append(ladder)
    prose = _prose(block_id(spec.id, deepening.number(len(blocks) + 1)), split.facts, cited)
    if prose is not None:
        blocks.append(prose)
        placed = offered.placed(
            composed.component_labels, section_id=spec.id, first=deepening.number(len(blocks) + 1)
        )
        blocks += placed.blocks
        cited = joined_claims(cited, placed.cited)
    shown_facts = split.facts if prose is not None else ()
    open_questions = tuple(
        cited_sentence(f"{spec.id}.open.{n}", sentence, cited)
        for n, sentence in enumerate(split.open_questions, 1)
    )
    kept = (*shown_facts, *split.open_questions)
    return _Attempt(
        pack=pack,
        composed=composed,
        blocks=tuple(context.enrichment.marked(block) for block in blocks),
        open_questions=open_questions,
        cited=cited,
        evidence_ids=tuple(evidence for sentence in kept for evidence in sentence.evidence_ids),
        claim_ids=_claim_ids(blocks, open_questions),
    )


def _ladder(
    spec: SectionSpec, context: SectionContext, composed: ComposedAnswer, ordinal: int
) -> Block | None:
    records = context.process
    if records is None or spec.discipline != LADDER_DISCIPLINE or not composed.stage_ids:
        return None
    ladder_id = block_id(spec.id, ordinal)
    ladder = process_ladder(records, block_id=ladder_id, stage_ids=composed.stage_ids)
    if ladder is None:
        return None
    problems = ladder_problems(ladder, records)
    if problems:
        logger.warning("ladder %s refused: %s", ladder_id, "; ".join(problems))
        return None
    return ladder


def _prose(prose_id: str, facts: Sequence[KeptSentence], cited: CitedClaims) -> Block | None:
    if not facts:
        return None
    try:
        return prose_block(prose_id, facts, cited)
    except BlockRefused as refused:
        logger.warning("%s", refused)
        return None


async def _shown(
    spec: SectionSpec,
    attempt: _Attempt,
    context: SectionContext,
    pictures: PictureSearches,
    builds: SectionBuilds,
) -> tuple[tuple[Block, ...], AddedBlocks]:
    sources = _section_sources(attempt.cited, context.process)
    texts = claim_texts(context.process, attempt.cited)
    in_language = partial(
        block_in_language, stream=context.stream, translation=context.tools.translation, claim_texts=texts
    )
    shown: list[Block] = list(attempt.floored)
    for block in attempt.blocks:
        shown += await context.stream.blocks(spec.id, [block], sources, in_language=in_language)
    deepening = context.deepening_of(spec.id)
    if deepening.adds_pictures:
        pictures.start(spec.id, shown)
    found = await builds.added(spec.id, first_ordinal=deepening.number(len(attempt.blocks) + 1))
    added = AddedBlocks(tuple(context.enrichment.marked(block) for block in found.blocks), found.sources)
    known = {**sources, **added.sources}
    shown += await context.stream.blocks(spec.id, added.blocks, known, in_language=in_language)
    ordinal = deepening.number(len(attempt.blocks) + len(added.blocks) + 1)
    images = await pictures.sent(spec.id, context.stream, ordinal=ordinal)
    if images is not None:
        shown.append(images)
    open_questions = await open_questions_in_language(
        attempt.open_questions,
        stream=context.stream,
        translation=context.tools.translation,
        claim_texts=texts,
    )
    await context.stream.open_questions(open_questions, sources)
    return tuple(shown), added


def _focus(spec: SectionSpec, context: SectionContext, offered: SectionCatalogue) -> ComposeFocus:
    records = context.process
    stages = ladder_stage_options(records) if records and spec.discipline == LADDER_DISCIPLINE else []
    return ComposeFocus(
        discipline=spec.discipline,
        title=DISCIPLINE_TITLES[spec.discipline],
        stages=stages,
        sentences_max=section_sentence_limit(context.base.depth),
        components=offered.options(),
    )


def _searched(blocks: Sequence[Block], attempt: _Attempt, packs: Sequence[EvidencePack]) -> str | None:
    if blocks:
        return None
    return COVERED_NOTE if attempt.blocks else searched_note(research_summary(*packs))


def _needs_fresh(attempt: _Attempt, floored: Sequence[Block]) -> bool:
    return not attempt.blocks and not floored and may_research_fresh(attempt.pack)


def _section_sources(cited: CitedClaims, records: ProcessRecords | None) -> dict[str, Mapping[str, Any]]:
    return {**process_sources(records), **cited.sources}


def _claim_ids(blocks: Sequence[Block], open_questions: Sequence[Mapping[str, Any]]) -> tuple[uuid.UUID, ...]:
    from_blocks = [citation.claim_id for block in blocks for citation in block.citations()]
    from_open = [citation["claimId"] for sentence in open_questions for citation in sentence["citations"]]
    return tuple(uuid.UUID(claim) for claim in dict.fromkeys([*from_blocks, *from_open]))


def _first_failure(group: BaseExceptionGroup) -> BaseException:
    leaves = list(_leaves(group))
    return next((leaf for leaf in leaves if isinstance(leaf, AppError)), leaves[0])


def _leaves(error: BaseException) -> Iterable[BaseException]:
    if isinstance(error, BaseExceptionGroup):
        for inner in error.exceptions:
            yield from _leaves(inner)
    else:
        yield error
