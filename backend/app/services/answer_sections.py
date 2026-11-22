from __future__ import annotations

import asyncio
import logging
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import replace
from functools import partial
from typing import Any

from app.composer.candidates import research_summary
from app.core.errors import AppError, spend_refusal
from app.research.blocks_component import stood_for
from app.research.evidence_pack import EvidencePack
from app.research.explainer import Block
from app.research.planning import ResearchShare
from app.research.research_summary import searched_note
from app.research.sections import SectionSpec
from app.science.records import ProcessRecords

from .answer_events import CitedClaims, joined_claims
from .block_builders import AddedBlocks, SectionBuilds
from .claim_ledger import COVERED_NOTE
from .research_ledger import may_research_fresh
from .reuse_enrichment import Floor, claim_texts, floor_sent, process_sources
from .seat_research import BuildAsk, section_ask
from .section_attempts import Attempt, attempt, claim_ids_of
from .section_context import SectionContext, SectionOutcome
from .section_enrichment import PictureSearches
from .section_headings import composed_heading
from .section_language import block_in_language, open_questions_in_language
from .section_trail import quote_trail

__all__ = ["SECTION_CONCURRENCY", "SECTION_STOPPED_NOTE", "run_sections", "started_order"]

logger = logging.getLogger(__name__)

SECTION_CONCURRENCY = 4
SECTION_STOPPED_NOTE = "Research for this section stopped before a source could be read."


async def run_sections(specs: Sequence[SectionSpec], context: SectionContext) -> list[SectionOutcome]:
    gate = asyncio.Semaphore(SECTION_CONCURRENCY)
    shares = dict(zip((spec.id for spec in specs), context.ledger.shares, strict=True))
    try:
        async with asyncio.TaskGroup() as group:
            tasks = {
                spec.id: group.create_task(_guarded(spec, shares[spec.id], context, gate))
                for spec in started_order(specs, context)
            }
    except BaseExceptionGroup as failed:
        raise _first_failure(failed) from None
    return [tasks[spec.id].result() for spec in specs]


def started_order(specs: Sequence[SectionSpec], context: SectionContext) -> list[SectionSpec]:
    return sorted(specs, key=lambda spec: -context.fields.priority(spec.discipline))


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
        claims = claim_ids_of(floored, ())
        return SectionOutcome(spec, blocks=floored, searched=searched, failure=error, claim_ids=claims)


async def _section(
    spec: SectionSpec, share: ResearchShare, context: SectionContext, floor: Floor, floored: tuple[Block, ...]
) -> SectionOutcome:
    thin = context.fields.is_thin(spec.discipline) and not floored
    attempts = [await attempt(spec, context, context.ledger.take_section(share), fresh=thin)]
    fresh = context.ledger.take_fresh(share) if _needs_fresh(attempts[0], floored) else None
    if fresh is not None:
        await context.stream.section_state(spec.id, "RESEARCHING")
        attempts.append(await attempt(spec, context, fresh, fresh=True))
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
            dict.fromkeys([*claim_ids_of(floored, ()), *shown.claim_ids, *claim_ids_of(added.blocks, ())])
        ),
        sources=sources,
    )


async def _built_on(
    spec: SectionSpec, shown: Attempt, context: SectionContext, ask: BuildAsk
) -> tuple[tuple[Block, ...], AddedBlocks]:
    deepening = context.deepening_of(spec.id)
    shown_kinds = {*deepening.kinds, *stood_for(shown.blocks)}
    async with (
        context.enrichment.searching() as pictures,
        context.builders.without(shown_kinds, shown=deepening.keys).building() as builds,
    ):
        builds.start(ask)
        return await _shown(spec, shown, context, pictures, builds)


async def _shown(
    spec: SectionSpec,
    attempt: Attempt,
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


def _searched(blocks: Sequence[Block], attempt: Attempt, packs: Sequence[EvidencePack]) -> str | None:
    if blocks:
        return None
    return COVERED_NOTE if attempt.blocks else searched_note(research_summary(*packs))


def _needs_fresh(attempt: Attempt, floored: Sequence[Block]) -> bool:
    return not attempt.blocks and not floored and may_research_fresh(attempt.pack)


def _section_sources(cited: CitedClaims, records: ProcessRecords | None) -> dict[str, Mapping[str, Any]]:
    return {**process_sources(records), **cited.sources}


def _first_failure(group: BaseExceptionGroup) -> BaseException:
    leaves = list(_leaves(group))
    return next((leaf for leaf in leaves if isinstance(leaf, AppError)), leaves[0])


def _leaves(error: BaseException) -> Iterable[BaseException]:
    if isinstance(error, BaseExceptionGroup):
        for inner in error.exceptions:
            yield from _leaves(inner)
    else:
        yield error
