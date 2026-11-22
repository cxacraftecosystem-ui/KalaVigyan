from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from dataclasses import KW_ONLY, dataclass, field
from typing import Any, Self

from app.core.errors import InvalidInput
from app.models.enums import DISCIPLINES, EXPLAINER_DEPTHS
from app.research.block_identity import repeats_shown
from app.research.depth import depth_at_least
from app.research.expert_panel import PANEL_FIELDS
from app.research.explainer import BLOCK_PHASES, BUILT_BLOCK_KINDS, Block
from app.research.piece_reuse import REGION_STORY_FACETS, SIMULATION_FACETS
from app.research.sections import block_id

from .artisan_voice_builder import ARTISAN_VOICE_FIELDS, ArtisanVoiceBuilder
from .builder_interface import BlockBuilder, BuildAsk, BuilderTools, Built, SourceRefs
from .builder_record import (
    ADDED,
    FAILED,
    NOTHING,
    TIMED_OUT,
    BuilderOutcome,
    BuildRecord,
)
from .claim_ledger import ONCE_PER_ANSWER_KINDS
from .climate_risk import CLIMATE_RISK_WAIT_SECONDS, ClimateRiskBuilder
from .expert_views import EXPERT_VIEW_WAIT_SECONDS, ExpertPanelBuilder
from .journey_builders import (
    TIMELINE_MAP_WAIT_SECONDS,
    ZOOM_STORY_WAIT_SECONDS,
    TimelineMapBuilder,
    ZoomStoryBuilder,
)
from .learning_builders import COMPARE_FIELDS, CONCEPT_GRAPH_FIELDS, CompareBuilder, ConceptGraphBuilder
from .market_builder import MARKET_FIELDS, MarketGiBuilder
from .matter_builders import (
    MATERIAL_CARD_WAIT_SECONDS,
    PLAYED_FIELDS,
    MaterialCardBuilder,
    MoleculeBuilder,
    ReactionPlayerBuilder,
)
from .measure_builder import MEASURE_FIELDS, MeasureBuilder
from .place_builders import REGION_STORY_WAIT_SECONDS, MapLayerBuilder, RegionStoryBuilder
from .season_supply_builders import SUPPLY_MAP_WAIT_SECONDS, SeasonsBuilder, SupplyMapBuilder
from .simulation_builder import SIMULATION_WAIT_SECONDS, SimulationBuilder
from .what_if_builder import WHAT_IF_FIELDS, WHAT_IF_WAIT_SECONDS, WhatIfBuilder

__all__ = [
    "BLOCK_BUILDERS",
    "BUILDER_WAIT_MAX_SECONDS",
    "BUILDER_WAIT_SECONDS",
    "SEASONS_FIELDS",
    "SUPPLY_MAP_FIELDS",
    "TIMELINE_MAP_FIELDS",
    "ZOOM_STORY_FIELDS",
    "AddedBlocks",
    "BlockBuilders",
    "BuilderEntry",
    "SectionBuilds",
    "built_by_registry",
]

logger = logging.getLogger(__name__)

BUILDER_WAIT_SECONDS = 8.0
BUILDER_WAIT_MAX_SECONDS = 180.0
PICTURES_KIND = "images"
PHASE_A = "A"
FIRST_DEPTH = EXPLAINER_DEPTHS[0]
EXPERT_DEPTH = EXPLAINER_DEPTHS[-1]
SEASONS_FIELDS = frozenset({"CLIMATE", "PROCESS", "GEOGRAPHY"})
SUPPLY_MAP_FIELDS = frozenset({"MATERIALS", "PROCESS", "ECONOMICS"})
ZOOM_STORY_FIELDS = frozenset({"MATERIALS", "CHEMISTRY", "PROCESS"})
TIMELINE_MAP_FIELDS = frozenset({"HISTORY", "ECONOMICS", "GEOGRAPHY"})


@dataclass(frozen=True)
class BuilderEntry:
    kind: str
    disciplines: frozenset[str]
    make: Callable[[BuilderTools], BlockBuilder]
    wait_seconds: float = BUILDER_WAIT_SECONDS
    _: KW_ONLY
    rebuilt_on_reuse: bool = False
    replaces_stored: bool = False
    reused_from: str = FIRST_DEPTH
    places_pieces: bool = False
    adds_pictures: bool = False
    prefers: str | None = None

    def builds_in(self, discipline: str, answer_fields: Collection[str]) -> bool:
        preferred = self.prefers
        return preferred is None or preferred == discipline or preferred not in answer_fields

    def __post_init__(self) -> None:
        if BLOCK_PHASES.get(self.kind, PHASE_A) == PHASE_A:
            raise InvalidInput(f"a builder adds a later phase's block kind, not {self.kind!r}")
        if not self.disciplines or not self.disciplines <= set(DISCIPLINES):
            raise InvalidInput(f"the {self.kind} builder names the fields it adds blocks to")
        if not 0 < self.wait_seconds <= BUILDER_WAIT_MAX_SECONDS:
            raise InvalidInput(f"the {self.kind} builder waits at most {BUILDER_WAIT_MAX_SECONDS} s")
        if self.replaces_stored and not self.rebuilt_on_reuse:
            raise InvalidInput(f"the {self.kind} builder replaces a stored block only when rebuilt on reuse")
        if self.reused_from not in EXPLAINER_DEPTHS:
            raise InvalidInput(f"the {self.kind} builder names the depth it is reused from")
        if self.prefers is not None and self.prefers not in self.disciplines:
            raise InvalidInput(f"the {self.kind} builder prefers a field it adds blocks to")


BLOCK_BUILDERS: tuple[BuilderEntry, ...] = (
    BuilderEntry(
        "region_story",
        REGION_STORY_FACETS,
        RegionStoryBuilder,
        REGION_STORY_WAIT_SECONDS,
        rebuilt_on_reuse=True,
    ),
    BuilderEntry("map_layer", frozenset({"GEOLOGY", "CLIMATE"}), MapLayerBuilder, rebuilt_on_reuse=True),
    BuilderEntry("seasons", SEASONS_FIELDS, SeasonsBuilder, prefers="CLIMATE"),
    BuilderEntry(
        "climate_risk",
        frozenset({"CLIMATE"}),
        ClimateRiskBuilder,
        CLIMATE_RISK_WAIT_SECONDS,
        rebuilt_on_reuse=True,
    ),
    BuilderEntry("supply_map", SUPPLY_MAP_FIELDS, SupplyMapBuilder, SUPPLY_MAP_WAIT_SECONDS),
    BuilderEntry("measure", MEASURE_FIELDS, MeasureBuilder),
    BuilderEntry("market_gi", MARKET_FIELDS, MarketGiBuilder, rebuilt_on_reuse=True),
    BuilderEntry(
        "reaction_player", PLAYED_FIELDS, ReactionPlayerBuilder, rebuilt_on_reuse=True, replaces_stored=True
    ),
    BuilderEntry(
        "material_card",
        frozenset({"CHEMISTRY", "MATERIALS"}),
        MaterialCardBuilder,
        MATERIAL_CARD_WAIT_SECONDS,
    ),
    BuilderEntry(
        "molecule_3d", frozenset({"CHEMISTRY", "MATERIALS"}), MoleculeBuilder, rebuilt_on_reuse=True
    ),
    BuilderEntry(
        "expert_view", PANEL_FIELDS, ExpertPanelBuilder, EXPERT_VIEW_WAIT_SECONDS, reused_from=EXPERT_DEPTH
    ),
    BuilderEntry("artisan_voice", ARTISAN_VOICE_FIELDS, ArtisanVoiceBuilder, rebuilt_on_reuse=True),
    BuilderEntry("what_if", WHAT_IF_FIELDS, WhatIfBuilder, WHAT_IF_WAIT_SECONDS),
    BuilderEntry(
        "simulation",
        SIMULATION_FACETS,
        SimulationBuilder,
        SIMULATION_WAIT_SECONDS,
        reused_from=EXPERT_DEPTH,
        places_pieces=True,
        adds_pictures=True,
    ),
    BuilderEntry("zoom_story", ZOOM_STORY_FIELDS, ZoomStoryBuilder, ZOOM_STORY_WAIT_SECONDS),
    BuilderEntry("timeline_map", TIMELINE_MAP_FIELDS, TimelineMapBuilder, TIMELINE_MAP_WAIT_SECONDS),
    BuilderEntry("compare", COMPARE_FIELDS, CompareBuilder, rebuilt_on_reuse=True),
    BuilderEntry("concept_graph", CONCEPT_GRAPH_FIELDS, ConceptGraphBuilder, rebuilt_on_reuse=True),
)

Pair = tuple[BuilderEntry, BlockBuilder]


@dataclass(frozen=True)
class AddedBlocks:
    blocks: tuple[Block, ...] = ()
    sources: SourceRefs = field(default_factory=dict)


class BlockBuilders:
    def __init__(
        self,
        builders: Iterable[Pair] = (),
        *,
        taken: set[str] | None = None,
        shown: Collection[str] = (),
        record: BuildRecord | None = None,
    ) -> None:
        self._builders = tuple(builders)
        self._taken = taken
        self._shown = frozenset(shown)
        self._record = record

    @classmethod
    def from_registry(
        cls,
        tools: BuilderTools,
        entries: Sequence[BuilderEntry] = BLOCK_BUILDERS,
        *,
        record: BuildRecord | None = None,
    ) -> Self:
        made = [(entry, entry.make(tools)) for entry in entries if entry.kind in BUILT_BLOCK_KINDS]
        return cls(made, record=record)

    def for_answer(self) -> BlockBuilders:
        return BlockBuilders(self._builders, taken=set(), record=self._record)

    def for_section(self, discipline: str) -> tuple[Pair, ...]:
        return tuple(pair for pair in self._builders if discipline in pair[0].disciplines)

    def for_reuse(self, shown: Collection[str], *, depth: str) -> BlockBuilders:
        return self._kept(
            pair
            for pair in self._builders
            if (pair[0].rebuilt_on_reuse or pair[0].kind not in shown)
            and depth_at_least(depth, pair[0].reused_from)
        )

    def replaced_on_reuse(self, discipline: str) -> frozenset[str]:
        return frozenset(entry.kind for entry, _ in self.for_section(discipline) if entry.replaces_stored)

    def without(self, kinds: Collection[str], *, shown: Collection[str] = ()) -> BlockBuilders:
        kept = (pair for pair in self._builders if pair[0].kind not in kinds)
        return BlockBuilders(kept, taken=self._taken, shown=shown, record=self._record)

    def note_shown(self, kinds: Iterable[str]) -> None:
        if self._taken is not None:
            self._taken.update(kind for kind in kinds if kind in ONCE_PER_ANSWER_KINDS)

    def building(self) -> SectionBuilds:
        return SectionBuilds(self)

    async def added(self, ask: BuildAsk) -> AddedBlocks:
        field = ask.section.discipline
        chosen = [
            pair
            for pair in self.for_section(field)
            if pair[0].builds_in(field, ask.answer_fields) and self._took(pair[0])
        ]
        if not chosen:
            return AddedBlocks()
        results = await asyncio.gather(*(_bounded(entry, builder, ask) for entry, builder in chosen))
        blocks: list[Block] = []
        sources: dict[str, Mapping[str, Any]] = {}
        outcomes: list[BuilderOutcome] = []
        for (entry, _), (built, seconds) in zip(chosen, results, strict=True):
            known = {**ask.cited.sources, **built.sources}
            checked = [block for block in _checked(entry, built, known, ask) if not self._repeats(block, ask)]
            if not checked:
                self._give_back(entry)
            blocks += checked
            sources.update({sid: known[sid] for block in checked for sid in block.cited_source_ids()})
            outcomes.append(_outcome(entry, built, len(checked), seconds))
        if self._record is not None:
            await self._record(ask.answer_id, ask.section.id, outcomes)
        return AddedBlocks(tuple(blocks), sources)

    def _kept(self, pairs: Iterable[Pair]) -> BlockBuilders:
        return BlockBuilders(pairs, taken=self._taken, shown=self._shown, record=self._record)

    def _repeats(self, block: Block, ask: BuildAsk) -> bool:
        if not repeats_shown(block, self._shown):
            return False
        logger.info(
            "a %s block of section %s is dropped: the section shows it already", block.kind, ask.section.id
        )
        return True

    def _took(self, entry: BuilderEntry) -> bool:
        if self._taken is None or entry.kind not in ONCE_PER_ANSWER_KINDS:
            return True
        if entry.kind in self._taken:
            return False
        self._taken.add(entry.kind)
        return True

    def _give_back(self, entry: BuilderEntry) -> None:
        if self._taken is not None and entry.kind in ONCE_PER_ANSWER_KINDS:
            self._taken.discard(entry.kind)


class SectionBuilds:
    def __init__(self, builders: BlockBuilders) -> None:
        self._builders = builders
        self._running: asyncio.Task[AddedBlocks] | None = None

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        running, self._running = self._running, None
        if running is not None:
            running.cancel()
            await asyncio.gather(running, return_exceptions=True)

    def start(self, ask: BuildAsk) -> None:
        if self._running is None and ask.blocks and self._builders.for_section(ask.section.discipline):
            self._running = asyncio.create_task(self._builders.added(ask))

    async def added(self, section_id: str, *, first_ordinal: int) -> AddedBlocks:
        running, self._running = self._running, None
        if running is None:
            return AddedBlocks()
        found = await running
        placed = tuple(
            block.model_copy(update={"id": block_id(section_id, first_ordinal + n)})
            for n, block in enumerate(found.blocks)
        )
        return AddedBlocks(placed, found.sources)


def built_by_registry(entries: Sequence[BuilderEntry] = BLOCK_BUILDERS) -> frozenset[str]:
    return frozenset(entry.kind for entry in entries)


async def _bounded(entry: BuilderEntry, builder: BlockBuilder, ask: BuildAsk) -> tuple[Built, float]:
    started = time.monotonic()
    try:
        async with asyncio.timeout(entry.wait_seconds):
            built = await builder.build(ask)
    except TimeoutError:
        logger.warning(
            "the %s builder for section %s took over %s s; it adds nothing",
            entry.kind,
            ask.section.id,
            entry.wait_seconds,
        )
        built = Built(note=TIMED_OUT)
    except Exception:
        logger.warning(
            "the %s builder for section %s failed; it adds nothing", entry.kind, ask.section.id, exc_info=True
        )
        built = Built(note=FAILED)
    return built, time.monotonic() - started


def _outcome(entry: BuilderEntry, built: Built, shown: int, seconds: float) -> BuilderOutcome:
    return BuilderOutcome(entry.kind, built.note or (ADDED if shown else NOTHING), shown, seconds)


def _checked(entry: BuilderEntry, built: Built, known: SourceRefs, ask: BuildAsk) -> list[Block]:
    checked: list[Block] = []
    for block in built.blocks:
        refusal = _refusal(entry, block, known)
        if refusal is None:
            checked.append(block)
        else:
            logger.warning("a %s block of section %s is dropped: %s", entry.kind, ask.section.id, refusal)
    return checked


def _refusal(entry: BuilderEntry, block: Block, known: SourceRefs) -> str | None:
    if block.kind != entry.kind and not (entry.adds_pictures and block.kind == PICTURES_KIND):
        return f"the {entry.kind} builder made a {block.kind} block"
    if block.kind not in BUILT_BLOCK_KINDS:
        return f"{block.kind} is not built yet"
    if block.reuse is not None and not entry.places_pieces:
        return "a built block carries no reuse mark"
    unknown = [sid for sid in block.cited_source_ids() if sid not in known]
    if unknown:
        return f"it cites sources the builder did not return: {', '.join(unknown)}"
    return None
