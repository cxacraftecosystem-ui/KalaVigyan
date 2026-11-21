from __future__ import annotations

import asyncio
import uuid
from collections.abc import Awaitable, Mapping, Sequence
from contextlib import AsyncExitStack
from dataclasses import dataclass, replace
from functools import partial
from typing import Any

from app.models.enums import EXPLAINER_DEPTHS
from app.research.blocks import ProcessLadderBlock
from app.research.explainer import Block
from app.research.planning import PlanRequest
from app.research.sections import LADDER_DISCIPLINE, SectionSpec, named_stage_ids
from app.science.ladder import ladder_problems, ladder_stage_options, process_ladder
from app.science.records import ProcessRecords

from .answer_lede import Opening
from .answer_sections import SectionOutcome
from .answer_translation import AnswerTranslation
from .block_builders import AddedBlocks, BlockBuilders, SectionBuilds
from .builder_interface import BuildAsk
from .claim_ledger import COVERED_NOTE, admission_batches
from .explainer_events import ExplainerStream, shown_title
from .piece_lookup import PieceLookup, ReusedSection
from .reuse_enrichment import Placed, claim_texts, kept_with_reuse, placed_section, process_sources
from .section_enrichment import Enrichment, PictureSearches
from .section_headings import Headed, headed_specs, heading_supports
from .section_language import block_in_language

__all__ = ["REUSED_SECTION_STATE", "ReuseBuilds", "ReusedShowing", "stream_reused", "stream_reused_beside"]

REUSED_SECTION_STATE = "WRITING"
DEEPEST_DEPTH = EXPLAINER_DEPTHS[-1]
ASKED_LADDER_SUFFIX = "ladder"


@dataclass(frozen=True)
class ReuseBuilds:
    builders: BlockBuilders
    answer_id: uuid.UUID
    request: PlanRequest
    process: ProcessRecords | None = None

    def placed(self, spec: SectionSpec, reused: ReusedSection, enrichment: Enrichment) -> Placed:
        replaced = self.builders.replaced_on_reuse(spec.discipline)
        placed = placed_section(spec, reused, enrichment, self.process, replaced=replaced)
        ladder = self._asked_ladder(spec, placed)
        return placed if ladder is None else _with_ladder(placed, enrichment.marked(ladder))

    def _asked_ladder(self, spec: SectionSpec, placed: Placed) -> ProcessLadderBlock | None:
        records = self.process
        if records is None or spec.discipline != LADDER_DISCIPLINE:
            return None
        shown = [block for block in placed.blocks if isinstance(block, ProcessLadderBlock)]
        held = [stage.stage_id for ladder in shown for stage in ladder.stages]
        wanted = named_stage_ids(self.request, ladder_stage_options(records), held)
        if set(wanted) <= set(held):
            return None
        ladder_id = shown[0].id if shown else f"{spec.id}.{ASKED_LADDER_SUFFIX}"
        ladder = process_ladder(records, block_id=ladder_id, stage_ids=wanted)
        if ladder is None or ladder_problems(ladder, records):
            return None
        return ladder

    async def started(
        self, stack: AsyncExitStack, spec: SectionSpec, placed: Placed, reused: ReusedSection
    ) -> SectionBuilds:
        builders = self.builders.for_reuse(placed.kinds, depth=self.request.depth or DEEPEST_DEPTH)
        builds = await stack.enter_async_context(builders.building())
        builds.start(BuildAsk(self.answer_id, spec, self.request, placed.blocks, reused.cited))
        return builds


@dataclass(frozen=True)
class ReusedShowing:
    stream: ExplainerStream
    titles: Mapping[str, str]
    translation: AnswerTranslation
    enrichment: Enrichment
    builds: ReuseBuilds
    opening: Awaitable[Opening] | None = None


@dataclass(frozen=True)
class _Reused:
    spec: SectionSpec
    reused: ReusedSection
    placed: Placed
    builds: SectionBuilds
    shown_title: str | None = None


async def stream_reused(
    specs: Sequence[SectionSpec], lookup: PieceLookup, showing: ReusedShowing
) -> list[SectionOutcome]:
    chosen = [
        (spec, lookup.reused[spec.discipline])
        for spec in sorted(specs, key=lambda spec: spec.order)
        if spec.discipline in lookup.reused
    ]
    builds = showing.builds
    placed = {spec.id: builds.placed(spec, reused, showing.enrichment) for spec, reused in chosen}
    builds.builders.note_shown(kind for one in placed.values() for kind in one.kinds)
    async with AsyncExitStack() as stack:
        running = {
            spec.id: await builds.started(stack, spec, placed[spec.id], reused) for spec, reused in chosen
        }
        headed = await _headed(chosen, placed, showing)
        shown = replace(showing, titles={**showing.titles, **{h.spec.id: h.shown for h in headed if h.shown}})
        sections = [
            _Reused(h.spec, reused, placed[h.spec.id], running[h.spec.id], h.shown)
            for h, (_, reused) in zip(headed, chosen, strict=True)
        ]
        async with shown.enrichment.searching() as pictures:
            opened = [await _opened(section, shown, pictures) for section in sections]
            return [
                await _closed(section, sent, shown, pictures)
                for section, sent in zip(sections, opened, strict=True)
            ]


async def stream_reused_beside(
    specs: Sequence[SectionSpec],
    lookup: PieceLookup,
    showing: ReusedShowing,
    research: Awaitable[list[SectionOutcome]],
) -> tuple[list[SectionOutcome], list[SectionOutcome]]:
    researching = asyncio.ensure_future(research)
    try:
        reused = await stream_reused(specs, lookup, showing)
        return reused, await researching
    finally:
        researching.cancel()
        await asyncio.gather(researching, return_exceptions=True)


async def _headed(
    chosen: Sequence[tuple[SectionSpec, ReusedSection]],
    placed: Mapping[str, Placed],
    showing: ReusedShowing,
) -> list[Headed]:
    if showing.opening is None or not chosen:
        return [Headed(spec) for spec, _ in chosen]
    opened = await showing.opening
    shown = [(spec, heading_supports(placed[spec.id].blocks, reused.cited)) for spec, reused in chosen]
    language = showing.stream.language
    return await headed_specs(opened.headings, shown, language=language, translation=showing.translation)


async def _opened(section: _Reused, showing: ReusedShowing, pictures: PictureSearches) -> list[Block]:
    spec, stream = section.spec, showing.stream
    title = shown_title(spec, showing.titles)["title"]
    for piece in section.reused.pieces:
        await stream.trail.found_piece(piece.id, title=title, stored_at=piece.created_at)
    await stream.section_started(spec, titles=showing.titles, state=REUSED_SECTION_STATE)
    shown: list[Block] = []
    for batch in admission_batches(section.placed.blocks):
        shown += await _sent(section, batch, showing, _placed_sources(section, showing))
    pictures.start(spec.id, shown)
    return shown


async def _closed(
    section: _Reused, shown: Sequence[Block], showing: ReusedShowing, pictures: PictureSearches
) -> SectionOutcome:
    spec, placed, stream = section.spec, section.placed, showing.stream
    first = len(placed.blocks) + 1
    rebuilt = await _rebuilt(spec, section.builds, showing, first_ordinal=first)
    sources = {**_placed_sources(section, showing), **rebuilt.sources}
    sent = [*shown, *await _sent(section, rebuilt.blocks, showing, sources)]
    images = await pictures.sent(spec.id, stream, ordinal=first + len(rebuilt.blocks))
    if images is not None:
        sent.append(images)
    searched = None if sent else COVERED_NOTE
    await stream.section_done(spec.id, searched=searched)
    rested = [*(claim for piece in section.reused.pieces for claim in piece.claim_ids), *_cited_claims(sent)]
    return SectionOutcome(
        spec,
        shown_title=section.shown_title,
        blocks=tuple(sent),
        built=kept_with_reuse(placed, rebuilt.blocks),
        searched=searched,
        claim_ids=tuple(dict.fromkeys(rested)),
        sources={**sources, **stream.shown_sources()},
    )


async def _rebuilt(
    spec: SectionSpec, builds: SectionBuilds, showing: ReusedShowing, *, first_ordinal: int
) -> AddedBlocks:
    found = await builds.added(spec.id, first_ordinal=first_ordinal)
    return AddedBlocks(tuple(showing.enrichment.marked(block) for block in found.blocks), found.sources)


async def _sent(
    section: _Reused,
    blocks: Sequence[Block],
    showing: ReusedShowing,
    sources: Mapping[str, Mapping[str, Any]],
) -> list[Block]:
    texts = claim_texts(showing.builds.process, section.reused.cited)
    in_language = partial(
        block_in_language, stream=showing.stream, translation=showing.translation, claim_texts=texts
    )
    return await showing.stream.blocks(section.spec.id, blocks, sources, in_language=in_language)


def _with_ladder(placed: Placed, ladder: Block) -> Placed:
    others = tuple(block for block in placed.blocks if not isinstance(block, ProcessLadderBlock))
    return replace(
        placed,
        blocks=(ladder, *others),
        built=(ladder, *(block for block in placed.built if not isinstance(block, ProcessLadderBlock))),
        copies=tuple(block for block in placed.copies if not isinstance(block, ProcessLadderBlock)),
    )


def _placed_sources(section: _Reused, showing: ReusedShowing) -> dict[str, Mapping[str, Any]]:
    return {**process_sources(showing.builds.process), **section.reused.cited.sources}


def _cited_claims(blocks: Sequence[Block]) -> list[uuid.UUID]:
    return [uuid.UUID(citation.claim_id) for block in blocks for citation in block.citations()]
