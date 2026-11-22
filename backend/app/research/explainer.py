from __future__ import annotations

import uuid
from collections.abc import Iterator, Mapping
from types import MappingProxyType
from typing import Annotated, Any, Literal, Self

from pydantic import AwareDatetime, Field, TypeAdapter, model_validator

from .base import ContractModel, absent
from .blocks import (
    BlockBase,
    ImagesBlock,
    ProcessLadderBlock,
    ProseBlock,
    SentenceChange,
    SentenceSpec,
    sentences_in_payload,
    with_sentences_in_payload,
)
from .blocks_climate import ClimateRiskBlock
from .blocks_component import ComponentBlock
from .blocks_insight import MarketGiBlock, MeasureBlock
from .blocks_journey import TimelineMapBlock, ZoomStoryBlock
from .blocks_learning import CompareBlock, ConceptGraphBlock, QuizBlock
from .blocks_lede import LEDE_KIND, LedeBlock
from .blocks_matter import MaterialCardBlock, Molecule3dBlock, ReactionPlayerBlock
from .blocks_people import (
    ArtisanVoiceBlock,
    DesignsBlock,
    ExpertViewBlock,
    InPracticeBlock,
    OpenQuestionsBlock,
    expert_pairing_problems,
)
from .blocks_place import MapLayerBlock, RegionStoryBlock, SeasonsBlock, SupplyMapBlock
from .blocks_play import SimulationBlock, WhatIfBlock
from .blocks_signature import FiringBlock, IndigoVatBlock, LostWaxBlock, MordantBathBlock
from .citations import SourceRef
from .composition import FOLLOW_UPS_MAX, HEADING_MAX_CHARS
from .crafts import MAX_CANDIDATES, QUESTION_MAX_CHARS, CraftRef
from .trail import PacedEvent, TrailEvent
from .vocabulary import AnswerLanguage, Depth, Discipline

__all__ = [
    "BLOCK_MODELS",
    "BLOCK_PHASES",
    "BUILT_BLOCK_KINDS",
    "BUILT_FIGURE_KINDS",
    "EXPLAINER_EVENTS",
    "EXPLAINER_SCHEMA_VERSION",
    "FINAL_SECTION_STATES",
    "SEARCHED_MAX_CHARS",
    "SECTION_ID_PATTERN",
    "SECTION_STATES",
    "SIGNATURE_PHASE",
    "UNDERSTANDING_BASES",
    "WORKING_SECTION_STATES",
    "Block",
    "BlockEvent",
    "Explainer",
    "ExplainerSection",
    "LedeEvent",
    "SectionDoneEvent",
    "SectionHeadingEvent",
    "SectionStartedEvent",
    "SectionStateEvent",
    "UnderstandingBasis",
    "Understood",
    "explainer_blocks",
    "payload_sentences",
    "with_payload_sentences",
]

EXPLAINER_SCHEMA_VERSION = 1
UNDERSTANDING_BASES = ("MODEL", "RESOLVER")

UnderstandingBasis = Literal[*UNDERSTANDING_BASES]
SECTION_ID_PATTERN = r"^s[1-9]\d{0,2}$"
SEARCHED_MAX_CHARS = 2000
WORKING_SECTION_STATES = ("RESEARCHING", "WRITING", "CHECKING")
FINAL_SECTION_STATES = ("READY", "EMPTY")
SECTION_STATES = (*WORKING_SECTION_STATES, *FINAL_SECTION_STATES)
SIGNATURE_PHASE = "SIGNATURE"

WorkingState = Literal[*WORKING_SECTION_STATES]
FinalState = Literal[*FINAL_SECTION_STATES]
SectionId = Annotated[str, Field(pattern=SECTION_ID_PATTERN)]

BLOCK_MODELS: Mapping[str, type[BlockBase]] = MappingProxyType(
    {
        "prose": ProseBlock,
        "process_ladder": ProcessLadderBlock,
        "region_story": RegionStoryBlock,
        "map_layer": MapLayerBlock,
        "reaction_player": ReactionPlayerBlock,
        "material_card": MaterialCardBlock,
        "molecule_3d": Molecule3dBlock,
        "images": ImagesBlock,
        "simulation": SimulationBlock,
        "what_if": WhatIfBlock,
        "timeline_map": TimelineMapBlock,
        "zoom_story": ZoomStoryBlock,
        "expert_view": ExpertViewBlock,
        "seasons": SeasonsBlock,
        "supply_map": SupplyMapBlock,
        "compare": CompareBlock,
        "in_practice": InPracticeBlock,
        "quiz": QuizBlock,
        "open_questions": OpenQuestionsBlock,
        "artisan_voice": ArtisanVoiceBlock,
        "designs": DesignsBlock,
        "concept_graph": ConceptGraphBlock,
        "measure": MeasureBlock,
        "market_gi": MarketGiBlock,
        "climate_risk": ClimateRiskBlock,
        "indigo_vat": IndigoVatBlock,
        "mordant_bath": MordantBathBlock,
        "lost_wax": LostWaxBlock,
        "firing": FiringBlock,
        "component": ComponentBlock,
    }
)
BLOCK_PHASES: Mapping[str, str] = MappingProxyType(
    {
        "prose": "A",
        "process_ladder": "A",
        "images": "A",
        "region_story": "B",
        "map_layer": "B",
        "reaction_player": "B",
        "material_card": "B",
        "molecule_3d": "B",
        "expert_view": "B",
        "seasons": "B",
        "supply_map": "B",
        "simulation": "C",
        "what_if": "C",
        "zoom_story": "C",
        "timeline_map": "C",
        "quiz": "D",
        "compare": "D",
        "in_practice": "D",
        "open_questions": "D",
        "concept_graph": "D",
        "measure": "D",
        "market_gi": "D",
        "climate_risk": "D",
        "artisan_voice": "E",
        "designs": "DEFERRED",
        "indigo_vat": SIGNATURE_PHASE,
        "mordant_bath": SIGNATURE_PHASE,
        "lost_wax": SIGNATURE_PHASE,
        "firing": SIGNATURE_PHASE,
        "component": "A",
    }
)
SENTENCE_MODELS: Mapping[str, type[BlockBase]] = MappingProxyType({**BLOCK_MODELS, LEDE_KIND: LedeBlock})
BUILT_BLOCK_KINDS = (
    "prose",
    "process_ladder",
    "images",
    "region_story",
    "map_layer",
    "expert_view",
    "seasons",
    "supply_map",
    "reaction_player",
    "material_card",
    "molecule_3d",
    "compare",
    "concept_graph",
    "climate_risk",
    "measure",
    "market_gi",
    "simulation",
    "what_if",
    "zoom_story",
    "timeline_map",
    "component",
)
BUILT_FIGURE_KINDS = ("indigo_vat", "mordant_bath", "lost_wax", "firing")

Block = Annotated[
    ProseBlock
    | ProcessLadderBlock
    | RegionStoryBlock
    | MapLayerBlock
    | ReactionPlayerBlock
    | MaterialCardBlock
    | Molecule3dBlock
    | ImagesBlock
    | SimulationBlock
    | WhatIfBlock
    | TimelineMapBlock
    | ZoomStoryBlock
    | ExpertViewBlock
    | SeasonsBlock
    | SupplyMapBlock
    | CompareBlock
    | InPracticeBlock
    | QuizBlock
    | OpenQuestionsBlock
    | ArtisanVoiceBlock
    | DesignsBlock
    | ConceptGraphBlock
    | MeasureBlock
    | MarketGiBlock
    | ClimateRiskBlock
    | IndigoVatBlock
    | MordantBathBlock
    | LostWaxBlock
    | FiringBlock
    | ComponentBlock,
    Field(discriminator="kind"),
]


class Understood(ContractModel):
    crafts: list[CraftRef] = Field(max_length=MAX_CANDIDATES)
    candidates: list[CraftRef] = Field(max_length=MAX_CANDIDATES)
    depth: Depth
    language: AnswerLanguage
    basis: UnderstandingBasis | None = Field(default=None, exclude_if=absent)

    @model_validator(mode="after")
    def _each_craft_once(self) -> Self:
        slugs = [craft.slug for craft in (*self.crafts, *self.candidates)]
        if len(set(slugs)) != len(slugs):
            raise ValueError("a craft is chosen or offered, once")
        return self


class SectionStartedEvent(ContractModel):
    id: SectionId
    discipline: Discipline
    title: str = Field(min_length=1, max_length=HEADING_MAX_CHARS)
    original: str | None = Field(default=None, min_length=1, exclude_if=absent)
    order: int = Field(ge=1)
    state: WorkingState


class SectionStateEvent(ContractModel):
    section_id: SectionId
    state: WorkingState


class BlockEvent(ContractModel):
    section_id: SectionId
    block: Block

    @model_validator(mode="after")
    def _only_blocks_the_reader_can_see(self) -> Self:
        _require_built(self.block)
        return self


class SectionDoneEvent(ContractModel):
    section_id: SectionId
    state: FinalState
    searched: str | None = Field(min_length=1, max_length=SEARCHED_MAX_CHARS)

    @model_validator(mode="after")
    def _an_empty_section_says_what_it_searched(self) -> Self:
        _require_searched(self.section_id, self.state, self.searched)
        return self


class SectionHeadingEvent(ContractModel):
    section_id: SectionId
    title: str = Field(min_length=1, max_length=HEADING_MAX_CHARS)
    original: str | None = Field(default=None, min_length=1, exclude_if=absent)


class LedeEvent(ContractModel):
    block: LedeBlock

    @model_validator(mode="after")
    def _a_figure_the_reader_can_see(self) -> Self:
        _require_built_figure(self.block)
        return self


class ExplainerSection(ContractModel):
    id: SectionId
    discipline: Discipline
    title: str = Field(min_length=1, max_length=HEADING_MAX_CHARS)
    original: str | None = Field(default=None, min_length=1, exclude_if=absent)
    order: int = Field(ge=1)
    state: FinalState
    blocks: list[Block]
    searched: str | None = Field(min_length=1, max_length=SEARCHED_MAX_CHARS)
    withdrawn: int = Field(default=0, ge=0, exclude_if=lambda value: value == 0)

    @model_validator(mode="after")
    def _ready_with_blocks_or_empty_with_a_reason(self) -> Self:
        _require_searched(self.id, self.state, self.searched)
        if (self.state == "READY") != bool(self.blocks):
            raise ValueError(f"section {self.id} is READY exactly when it holds blocks")
        for block in self.blocks:
            _require_built(block)
        cited = set().union(*(block.cited_claim_ids() for block in self.blocks))
        if any(not block.illustrated_claim_ids() <= cited for block in self.blocks):
            raise ValueError(f"section {self.id} shows images only for claims it cites")
        pairing = expert_pairing_problems(self.blocks)
        if pairing:
            raise ValueError(f"section {self.id}: {'; '.join(pairing)}")
        return self


class Explainer(ContractModel):
    schema_version: Literal[1]
    answer_id: uuid.UUID
    question: str = Field(min_length=1, max_length=QUESTION_MAX_CHARS)
    understood: Understood
    lede: LedeBlock | None = Field(default=None, exclude_if=absent)
    sections: list[ExplainerSection] = Field(min_length=1)
    sources: list[SourceRef]
    follow_ups: list[str] = Field(max_length=FOLLOW_UPS_MAX)
    created_at: AwareDatetime

    @model_validator(mode="after")
    def _sections_in_order_and_sources_as_cited(self) -> Self:
        if self.lede is not None:
            _require_lede(self.lede, self.question)
        if [section.order for section in self.sections] != list(range(1, len(self.sections) + 1)):
            raise ValueError("sections are listed by order, 1 to n")
        if len({section.id for section in self.sections}) != len(self.sections):
            raise ValueError("each section id is used once")
        block_ids = [block.id for block in explainer_blocks(self)]
        if len(set(block_ids)) != len(block_ids):
            raise ValueError("each block id is used once")
        if all(section.state == "EMPTY" for section in self.sections):
            raise ValueError("an explainer shows at least one ready section")
        ordered = dict.fromkeys(sid for block in explainer_blocks(self) for sid in block.cited_source_ids())
        if [source.id for source in self.sources] != list(ordered):
            raise ValueError("sources lists every cited source once, in order of first citation")
        return self


def explainer_blocks(explainer: Explainer) -> Iterator[BlockBase]:
    if explainer.lede is not None:
        yield explainer.lede
    for section in explainer.sections:
        yield from section.blocks


def payload_sentences(payload: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    return sentences_in_payload(payload, _sentence_spec(payload))


def with_payload_sentences(payload: Mapping[str, Any], change: SentenceChange) -> dict[str, Any]:
    return with_sentences_in_payload(payload, _sentence_spec(payload), change)


def _sentence_spec(payload: Mapping[str, Any]) -> SentenceSpec:
    model = SENTENCE_MODELS.get(str(payload.get("kind")))
    if model is None:
        return ()
    figure = payload.get("figure")
    shown = SENTENCE_MODELS.get(str(figure.get("kind"))) if isinstance(figure, Mapping) else None
    return model.SENTENCES if shown is None else (*model.SENTENCES, ("figure", shown.SENTENCES))


def _require_built(block: BlockBase) -> None:
    if block.kind not in BUILT_BLOCK_KINDS:
        raise ValueError(f"block {block.id} is a {block.kind} block, which is not built yet")


def _require_built_figure(lede: LedeBlock) -> None:
    figure = lede.figure
    if figure is not None and figure.kind not in BUILT_FIGURE_KINDS:
        raise ValueError(f"figure {figure.id} is a {figure.kind} figure, which is not built yet")


def _require_lede(lede: LedeBlock, question: str) -> None:
    if lede.headline != question:
        raise ValueError("the lede's headline is the question as asked")
    _require_built_figure(lede)


def _require_searched(section_id: str, state: str, searched: str | None) -> None:
    if (state == "EMPTY") != (searched is not None):
        raise ValueError(f"section {section_id} says what it searched exactly when it is EMPTY")


EXPLAINER_EVENTS: Mapping[str, TypeAdapter[Any]] = MappingProxyType(
    {
        "understood": TypeAdapter(Understood),
        "section_started": TypeAdapter(SectionStartedEvent),
        "section_state": TypeAdapter(SectionStateEvent),
        "block": TypeAdapter(BlockEvent),
        "section_done": TypeAdapter(SectionDoneEvent),
        "section_heading": TypeAdapter(SectionHeadingEvent),
        "lede": TypeAdapter(LedeEvent),
        "trail": TypeAdapter(TrailEvent),
        "paced": TypeAdapter(PacedEvent),
    }
)
