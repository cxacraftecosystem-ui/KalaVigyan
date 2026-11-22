from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Protocol

from app.core.errors import AppError, spend_refusal
from app.planner.policy import request_limits
from app.research.composition import ComposedAnswer, ComposeRequest
from app.research.crafts import CraftRef
from app.research.depth import depth_policy
from app.research.evidence_pack import EvidencePack
from app.research.explainer import Explainer
from app.research.explainer_versions import VersionMark
from app.research.planning import PlanRequest
from app.research.reading_style import ReadingStyle
from app.research.sections import LADDER_DISCIPLINE, AnswerPlans, SectionSpec
from app.research.stream import Emit
from app.research.understanding import UnderstandAsk, Understanding, UnknownCraft
from app.research.vocabulary import CANONICAL_LANGUAGE
from app.science.records import ProcessRecords

from .answer_catalogue import CatalogueLookup, no_catalogue
from .answer_events import CitedClaims
from .answer_gaps import FieldReading, answer_readings
from .answer_lede import AnswerOpening, LedeTools, LedeWriting, Opening, lede_plan
from .answer_sections import run_sections
from .answer_translation import AnswerTranslation, Segment, translate_segments, with_english_question
from .block_builders import BlockBuilders
from .explainer_document import explainer_document
from .explainer_events import ExplainerStream, status_message
from .explainer_history import STALE_VERSION_DETAIL, StaleVersion
from .follow_ups import AnswerLayout, FollowUp, answer_layout, closed_answer, left_open, understood_for
from .piece_lookup import PieceAsk, PieceLookup, ReusedSection
from .piece_store import BuiltSection, PieceStore
from .research_ledger import ResearchLedger
from .reuse_enrichment import expert_floors, floor_deepening, floors_by_section
from .reused_sections import ReuseBuilds, ReusedShowing, stream_reused_beside
from .section_context import (
    ClaimsOf,
    Research,
    SectionContext,
    SectionOutcome,
    SectionTools,
    answer_plans,
)
from .section_enrichment import Enrichment, EnrichmentTools
from .section_fields import SectionFields
from .stored_fields import with_stored_fields
from .stored_only_answer import STORED_ONLY_MODE, stored_only_answer
from .write_back_names import CraftNames

__all__ = [
    "NOT_FOUND_DETAIL",
    "RESEARCH_FAILED_DETAIL",
    "RESOLVER_FAILED_DETAIL",
    "STORED_ONLY_MODE",
    "UNEXPECTED_DETAIL",
    "AnswerAsk",
    "AnswerPipeline",
    "AnswerStore",
    "NameLookup",
    "answer_question",
    "answer_understood",
    "status_message",
]

logger = logging.getLogger(__name__)

NOT_FOUND_DETAIL = "No craft has that address."
RESOLVER_FAILED_DETAIL = "Finding the craft failed just now. Try again."
RESEARCH_FAILED_DETAIL = "Research failed just now. Try again."
UNEXPECTED_DETAIL = "Something went wrong while answering. Try again."

NameLookup = Callable[[CraftRef | None, Sequence[CraftRef]], Awaitable[CraftNames]]


@dataclass(frozen=True)
class AnswerAsk:
    question: str
    depth: str
    craft_slug: str | None = None
    any_craft: bool = False
    language: str | None = None
    user_id: uuid.UUID | None = None
    role: str | None = None
    withheld_terms: tuple[str, ...] = ()
    fresh: bool = False
    builds_on: FollowUp | None = None
    reading_style: ReadingStyle | None = None
    asked_at: datetime = field(default_factory=lambda: datetime.now(UTC), compare=False)


class AnswerStore(Protocol):
    async def stored_claims(self, craft_slug: str, question: str, mode: str) -> CitedClaims: ...

    async def begin(self, ask: AnswerAsk, understanding: Understanding) -> uuid.UUID: ...

    async def keep(self, answer_id: uuid.UUID, pack: EvidencePack, composed: ComposedAnswer) -> ClaimsOf: ...

    async def cited(self, claim_ids: Iterable[uuid.UUID]) -> CitedClaims: ...

    async def process(self, craft_slug: str) -> ProcessRecords | None: ...

    async def finish(
        self,
        answer_id: uuid.UUID,
        *,
        asked_at: datetime,
        plans: AnswerPlans,
        claim_ids: Sequence[uuid.UUID],
        explainer: Explainer | None,
        version: VersionMark | None = None,
        readings: Sequence[FieldReading] = (),
    ) -> None: ...


@dataclass(frozen=True)
class AnswerPipeline:
    understand: Callable[[UnderstandAsk], Awaitable[Understanding]]
    research: Research
    compose: Callable[[ComposeRequest], Awaitable[ComposedAnswer]]
    store: AnswerStore
    translation: AnswerTranslation
    pieces: PieceStore
    enrichment: EnrichmentTools
    builders: BlockBuilders = field(default_factory=BlockBuilders)
    lede: LedeTools = field(default_factory=LedeTools)
    catalogue: CatalogueLookup = no_catalogue
    names: NameLookup | None = None


@dataclass(frozen=True)
class _Run:
    ask: AnswerAsk
    understanding: Understanding
    pipeline: AnswerPipeline
    stream: ExplainerStream
    answer_id: uuid.UUID
    enrichment: Enrichment
    layout: AnswerLayout
    process: ProcessRecords | None = None
    floors: Mapping[str, ReusedSection] = field(default_factory=dict)
    builders: BlockBuilders = field(default_factory=BlockBuilders)


async def answer_question(ask: AnswerAsk, pipeline: AnswerPipeline, emit: Emit) -> None:
    answer_id: uuid.UUID | None = None
    try:
        answer_id = await _answer(ask, pipeline, emit)
    except StaleVersion as stale:
        logger.warning("the follow-up was not kept: %s", stale)
        await emit("error", {"message": STALE_VERSION_DETAIL})
    except AppError as error:
        logger.warning("answering stopped: %s", error, exc_info=True)
        await emit("error", {"message": _user_message(error, RESEARCH_FAILED_DETAIL)})
    except Exception:
        logger.exception("answering failed")
        await emit("error", {"message": UNEXPECTED_DETAIL})
    await emit("done", {"answerId": str(answer_id) if answer_id else None})


async def answer_understood(
    ask: AnswerAsk, understanding: Understanding, pipeline: AnswerPipeline, emit: Emit
) -> uuid.UUID:
    return await _researched_answer(
        ask, understanding, pipeline, ExplainerStream(emit, language=_language(ask))
    )


async def _answer(ask: AnswerAsk, pipeline: AnswerPipeline, emit: Emit) -> uuid.UUID | None:
    understanding = await _understood(ask, pipeline, emit)
    if understanding is None:
        return None
    stream = ExplainerStream(emit, language=_language(ask))
    if understanding.refusal is not None:
        await _refused_answer(ask, understanding, pipeline, stream)
        return None
    return await _researched_answer(ask, understanding, pipeline, stream)


async def _understood(ask: AnswerAsk, pipeline: AnswerPipeline, emit: Emit) -> Understanding | None:
    request = UnderstandAsk(
        question=ask.question,
        depth=ask.depth,
        language=_language(ask),
        craft_slug=ask.craft_slug,
        any_craft=ask.any_craft,
        role=ask.role,
    )
    try:
        understanding = await pipeline.understand(request)
    except UnknownCraft:
        await emit("error", {"message": NOT_FOUND_DETAIL})
        return None
    except AppError as error:
        logger.warning("understanding the question failed", exc_info=True)
        await emit("error", {"message": _user_message(error, RESOLVER_FAILED_DETAIL)})
        return None
    await emit("understood", understood_for(understanding, ask.builds_on))
    if ask.builds_on is not None:
        await emit("builds_on", ask.builds_on.event())
    return understanding


async def _refused_answer(
    ask: AnswerAsk, understanding: Understanding, pipeline: AnswerPipeline, stream: ExplainerStream
) -> None:
    if understanding.craft is None or ask.builds_on is not None:
        await stream.emit("error", {"message": understanding.refusal})
        return
    await stored_only_answer(
        ask.question,
        understanding.craft,
        stored=pipeline.store.stored_claims,
        stream=stream,
        translation=pipeline.translation,
    )


async def _researched_answer(
    ask: AnswerAsk, understanding: Understanding, pipeline: AnswerPipeline, stream: ExplainerStream
) -> uuid.UUID:
    craft = understanding.craft
    await stream.status("PLANNING", craft=craft.name if craft else "")
    understanding = await _prepared(ask, understanding, pipeline, stream.language)
    layout = answer_layout(understanding, ask.builds_on, question=ask.question)
    specs = layout.specs
    answer_id = await pipeline.store.begin(ask, understanding)
    segments = [Segment(spec.id, spec.title) for spec in layout.untitled]
    translated = await translate_segments(
        segments, language=stream.language, translation=pipeline.translation
    )
    titles = {**translated, **layout.titles}
    looked = await pipeline.pieces.reusable(_piece_ask(ask, understanding, layout.reusable))
    lookup, floors = (looked, {}) if ask.builds_on else expert_floors(understanding.depth, looked)
    enrichment = await pipeline.enrichment.for_answer(craft)
    process = await _process(craft, specs, pipeline.store)
    builders = pipeline.builders.for_answer()
    run = _Run(ask, understanding, pipeline, stream, answer_id, enrichment, layout, process, floors, builders)
    writing = LedeWriting(stream, pipeline.translation, enrichment)
    plan = lede_plan(ask.question, understanding, layout.untitled, lookup, style=ask.reading_style)
    opening = AnswerOpening(plan, pipeline.lede, writing, pipeline.store)
    open_specs = [spec for spec in specs if spec.discipline not in lookup.reused]
    async with opening.started() as first_lede:
        for spec in open_specs:
            await stream.section_started(spec, titles=titles, state="RESEARCHING")
        showing = _reused_showing(run, titles, first_lede)
        reused, researched = await stream_reused_beside(specs, lookup, showing, _research(open_specs, run))
        first = await first_lede
    outcomes = sorted([*reused, *researched], key=lambda outcome: outcome.spec.order)
    opened = await opening.settled(first, outcomes)
    offered = left_open(ask.question, understanding, outcomes, opened)
    follow_ups = await closed_answer(outcomes, offered, stream, pipeline.translation)
    await _finish(run, outcomes, titles=titles, follow_ups=follow_ups, opened=opened)
    await _kept(run, lookup, outcomes)
    return answer_id


async def _prepared(
    ask: AnswerAsk, understanding: Understanding, pipeline: AnswerPipeline, language: str
) -> Understanding:
    if ask.builds_on is None:
        understanding = await with_stored_fields(understanding, pipeline.pieces.fields)
    return await with_english_question(
        understanding, question=ask.question, language=language, translation=pipeline.translation
    )


async def _kept(run: _Run, lookup: PieceLookup, outcomes: Sequence[SectionOutcome]) -> None:
    keeps = run.layout.keeps_pieces_of
    built = [
        BuiltSection(o.spec.discipline, o.built, deepened=not keeps(o.spec)) for o in outcomes if o.built
    ]
    style = run.ask.reading_style
    await run.pipeline.pieces.keep(
        lookup, answer_id=run.answer_id, depth=run.understanding.depth, sections=built, reading_style=style
    )


def _reused_showing(run: _Run, titles: Mapping[str, str], opening: Awaitable[Opening]) -> ReusedShowing:
    builds = ReuseBuilds(run.builders, run.answer_id, _plan_request(run.ask, run.understanding), run.process)
    return ReusedShowing(run.stream, titles, run.pipeline.translation, run.enrichment, builds, opening)


async def _research(specs: Sequence[SectionSpec], run: _Run) -> list[SectionOutcome]:
    if not specs:
        return []
    pipeline = run.pipeline
    base = _plan_request(run.ask, run.understanding)
    craft = run.understanding.craft
    held = await run.pipeline.pieces.fields(craft.slug) if craft is not None else ()
    fields = SectionFields.of(run.layout.asked(run.understanding), held, run.layout.specs)
    floors = floors_by_section(specs, run.floors, run.enrichment, run.process)
    deepening = {**run.layout.deepening, **{sid: floor_deepening(f.placed) for sid, f in floors.items()}}
    context = SectionContext(
        tools=SectionTools(
            pipeline.research, pipeline.compose, pipeline.store, pipeline.translation, pipeline.catalogue
        ),
        stream=run.stream,
        answer_id=run.answer_id,
        base=base,
        ledger=ResearchLedger(
            request_limits(base, base.mode), [fields.priority(spec.discipline) for spec in specs]
        ),
        enrichment=run.enrichment,
        process=run.process,
        builders=run.builders,
        deepening=deepening,
        floors=floors,
        reading_style=run.ask.reading_style,
        fields=fields,
        names=await _names(run),
    )
    return await run_sections(specs, context)


async def _names(run: _Run) -> CraftNames | None:
    found = run.pipeline.names
    return await found(run.understanding.craft, run.understanding.compared) if found else None


async def _finish(
    run: _Run,
    outcomes: Sequence[SectionOutcome],
    *,
    titles: Mapping[str, str],
    follow_ups: Sequence[str],
    opened: Opening,
) -> None:
    document = explainer_document(
        answer_id=run.answer_id,
        question=run.ask.question,
        understood=run.layout.understood(run.understanding),
        outcomes=outcomes,
        titles={**titles, **{o.spec.id: o.shown_title for o in outcomes if o.shown_title}},
        follow_ups=follow_ups,
        lede=opened.lede,
        lede_sources=opened.sources,
    )
    led = [uuid.UUID(citation.claim_id) for citation in opened.lede.citations()] if opened.lede else []
    stored = run.layout.stored(document, dict.fromkeys([*led, *(c for o in outcomes for c in o.claim_ids)]))
    await run.pipeline.store.finish(
        run.answer_id,
        asked_at=run.ask.asked_at,
        plans=answer_plans(outcomes),
        claim_ids=list(stored.claim_ids),
        explainer=stored.explainer,
        version=stored.version,
        readings=answer_readings(outcomes),
    )
    if stored.version is not None:
        await run.stream.emit("version", stored.version)


def _piece_ask(ask: AnswerAsk, understanding: Understanding, specs: Sequence[SectionSpec]) -> PieceAsk:
    return PieceAsk(
        question=ask.question,
        craft=understanding.craft,
        facets=tuple(spec.discipline for spec in specs),
        depth=understanding.depth,
        fresh=ask.fresh,
        reading_style=ask.reading_style,
    )


async def _process(
    craft: CraftRef | None, specs: Sequence[SectionSpec], store: AnswerStore
) -> ProcessRecords | None:
    if craft is None or all(spec.discipline != LADDER_DISCIPLINE for spec in specs):
        return None
    return await store.process(craft.slug)


def _plan_request(ask: AnswerAsk, understanding: Understanding) -> PlanRequest:
    return PlanRequest(
        question=ask.question,
        mode=depth_policy(understanding.depth).mode,
        craft=understanding.craft,
        compared=tuple(understanding.compared),
        depth=understanding.depth,
        language=_language(ask),
        withheld_terms=ask.withheld_terms,
        english_question=understanding.english_question,
        seats=tuple(understanding.seats),
    )


def _language(ask: AnswerAsk) -> str:
    return ask.language or CANONICAL_LANGUAGE


def _user_message(error: AppError, otherwise: str) -> str:
    return spend_refusal(error) or otherwise
