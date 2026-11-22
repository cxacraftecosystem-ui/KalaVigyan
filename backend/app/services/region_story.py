from __future__ import annotations

import dataclasses
import logging
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from pydantic import ValidationError

from app.composer.region_story import (
    NO_CHOICE,
    STORY_LAYERS_MAX,
    STORY_STEPS_MAX,
    StoryBrief,
    StoryChoice,
    StoryItem,
)
from app.research.blocks import ExplainerSentence, named_in
from app.research.blocks_place import DistrictRef, RegionStoryBlock, RiverPath, StoryStep
from app.research.datasets import BOUNDARY_CAPTION, BOUNDARY_DATASET_CODE, DatasetRef
from app.research.explainer import Block
from app.research.rivers import HYDRORIVERS_DATASET_CODE, RiverTrace
from app.science.records import KnownClaim

from .answer_events import CitedClaims
from .builder_evidence import section_facts

__all__ = [
    "DISTRICT_REF_PREFIX",
    "RIVER_DISTRICTS_OFFERED",
    "STORY_STATEMENTS_MAX",
    "LayerOffer",
    "OfferedRiver",
    "RegionOffer",
    "region_story_block",
    "story_brief",
    "story_statements",
]

logger = logging.getLogger(__name__)

STORY_STATEMENTS_MAX = 12
RIVER_DISTRICTS_OFFERED = 30
DISTRICT_REF_PREFIX = "d"


@dataclass(frozen=True)
class OfferedRiver:
    ref: str
    trace: RiverTrace
    ord_stra: int
    dis_av_cms: float
    name: str | None = None
    name_dataset: str | None = None


@dataclass(frozen=True)
class LayerOffer:
    id: str
    title: str
    dataset_code: str


@dataclass(frozen=True)
class RegionOffer:
    craft_districts: tuple[int, ...]
    rivers: tuple[OfferedRiver, ...]
    districts: Mapping[int, DistrictRef]
    layers: tuple[LayerOffer, ...]
    datasets: Mapping[str, DatasetRef]


def story_statements(blocks: Sequence[Block], cited: CitedClaims) -> dict[str, KnownClaim]:
    facts = section_facts(blocks, cited, limit=STORY_STATEMENTS_MAX)
    return {f"c{n}": claim for n, claim in enumerate(facts, start=1)}


def story_brief(offer: RegionOffer, statements: Mapping[str, KnownClaim]) -> StoryBrief:
    return StoryBrief(
        rivers=tuple(StoryItem(river.ref, _river_text(river, offer.districts)) for river in offer.rivers),
        districts=tuple(
            StoryItem(f"{DISTRICT_REF_PREFIX}{lgd}", _district_text(offer, lgd))
            for lgd in _offered_districts(offer)
        ),
        layers=tuple(StoryItem(layer.id, _layer_text(layer, offer.datasets)) for layer in offer.layers),
        statements=tuple(StoryItem(ref, claim.text) for ref, claim in statements.items()),
    )


def region_story_block(
    offer: RegionOffer, statements: Mapping[str, KnownClaim], choice: StoryChoice, *, block_id: str
) -> RegionStoryBlock | None:
    boundary = offer.datasets.get(BOUNDARY_DATASET_CODE)
    if boundary is None:
        logger.warning("no %s dataset row to cite beneath the map; no region story", BOUNDARY_DATASET_CODE)
        return None
    river = _story_river(offer, choice.river)
    listed = _listed_districts(offer, river)
    steps = _steps(choice, statements, [offer.districts[lgd] for lgd in listed], block_id)
    if not steps:
        logger.info("the region story %s chose no stored statement and is not shown", block_id)
        return None
    layers = _layers(choice.layers, offer)
    drawn = [boundary, *_river_rows(offer, river)]
    cited = [*drawn, *(offer.datasets[layer.dataset_code] for layer in layers)]
    datasets = list({row.code: row for row in cited}.values())
    try:
        return RegionStoryBlock(
            id=block_id,
            kind="region_story",
            version=1,
            reuse=None,
            river=_river_path(river),
            districts=[offer.districts[lgd] for lgd in listed],
            steps=steps,
            layers=[layer.id for layer in layers],
            datasets=datasets,
            boundary_caption=BOUNDARY_CAPTION,
        )
    except ValidationError as refused:
        logger.warning("the region story %s is refused: %s", block_id, refused)
        return None


def _story_river(offer: RegionOffer, ref: str) -> OfferedRiver | None:
    if ref == NO_CHOICE:
        return None
    river = next((river for river in offer.rivers if river.ref == ref), None)
    if river is None:
        logger.info("the region story names river %r, which was not offered", ref)
        return None
    if HYDRORIVERS_DATASET_CODE not in offer.datasets:
        logger.warning("no %s dataset row; the story is told without its river", HYDRORIVERS_DATASET_CODE)
        return None
    unnamed = [lgd for lgd in river.trace.district_lgds if lgd not in offer.districts]
    if unnamed:
        logger.warning("river %s reaches districts with no register row: %s", river.trace.main_riv, unnamed)
        return None
    if river.name_dataset is not None and river.name_dataset not in offer.datasets:
        logger.warning(
            "no %s dataset row; river %s is drawn unnamed", river.name_dataset, river.trace.main_riv
        )
        return dataclasses.replace(river, name=None, name_dataset=None)
    return river


def _river_rows(offer: RegionOffer, river: OfferedRiver | None) -> list[DatasetRef]:
    if river is None:
        return []
    named = [offer.datasets[river.name_dataset]] if river.name_dataset and river.name else []
    return [offer.datasets[HYDRORIVERS_DATASET_CODE], *named]


def _listed_districts(offer: RegionOffer, river: OfferedRiver | None) -> list[int]:
    first = list(river.trace.district_lgds) if river is not None else []
    rest = [lgd for lgd in offer.craft_districts if lgd not in first and lgd in offer.districts]
    return [*first, *rest]


def _steps(
    choice: StoryChoice, statements: Mapping[str, KnownClaim], listed: Sequence[DistrictRef], block_id: str
) -> list[StoryStep]:
    steps: list[StoryStep] = []
    taken: set[uuid.UUID] = set()
    for chosen in choice.steps:
        claim = statements.get(chosen.claim)
        if claim is None:
            logger.info(
                "the region story %s drops step %r: not one of its statements", block_id, chosen.claim
            )
            continue
        if claim.id in taken:
            continue
        taken.add(claim.id)
        sentence = ExplainerSentence(
            id=f"{block_id}.{len(steps) + 1}",
            text=claim.text,
            level=claim.level,
            citations=list(claim.citations),
            terms=[],
        )
        district = _district(chosen.district, listed)
        if district is not None and not named_in(district.name, sentence):
            logger.info(
                "the region story %s leaves a step unplaced: it does not name %s", block_id, district.name
            )
            district = None
        steps.append(StoryStep(district_lgd=district.district_lgd if district else None, sentence=sentence))
        if len(steps) == STORY_STEPS_MAX:
            break
    return steps


def _district(ref: str, listed: Sequence[DistrictRef]) -> DistrictRef | None:
    code = ref.removeprefix(DISTRICT_REF_PREFIX)
    if code == ref or not code.isdigit():
        return None
    return next((district for district in listed if district.district_lgd == int(code)), None)


def _river_path(river: OfferedRiver | None) -> RiverPath | None:
    if river is None:
        return None
    trace = river.trace
    return RiverPath(
        dataset_code=trace.dataset_code,
        main_riv=trace.main_riv,
        reach_ids=list(trace.reach_ids),
        district_lgds=list(trace.district_lgds),
        name=river.name,
    )


def _layers(refs: Iterable[str], offer: RegionOffer) -> list[LayerOffer]:
    offered = {layer.id: layer for layer in offer.layers}
    kept: list[LayerOffer] = []
    for ref in dict.fromkeys(refs):
        layer = offered.get(ref)
        if layer is None:
            logger.info("the region story names layer %r, which was not offered", ref)
        elif layer.dataset_code not in offer.datasets:
            logger.warning("layer %s is left out: no %s dataset row to cite", layer.id, layer.dataset_code)
        else:
            kept.append(layer)
    return kept[:STORY_LAYERS_MAX]


def _offered_districts(offer: RegionOffer) -> list[int]:
    reached = [lgd for river in offer.rivers for lgd in river.trace.district_lgds[:RIVER_DISTRICTS_OFFERED]]
    return [lgd for lgd in dict.fromkeys([*offer.craft_districts, *reached]) if lgd in offer.districts]


def _river_text(river: OfferedRiver, districts: Mapping[int, DistrictRef]) -> str:
    reached = [_place(districts[lgd]) for lgd in river.trace.district_lgds if lgd in districts]
    shown = reached[:RIVER_DISTRICTS_OFFERED]
    more = f", and {len(reached) - len(shown)} more" if len(reached) > len(shown) else ""
    named = f"Named {river.name} in the river names dataset {river.name_dataset}. " if river.name else ""
    return (
        f"{named}Strahler stream order {river.ord_stra}; mean discharge {river.dis_av_cms:g} m3/s. "
        f"From its source to its mouth it reaches: {'; '.join(shown)}{more}."
    )


def _district_text(offer: RegionOffer, lgd: int) -> str:
    place = _place(offer.districts[lgd])
    return f"{place}. The craft is practised here." if lgd in offer.craft_districts else place


def _layer_text(layer: LayerOffer, datasets: Mapping[str, DatasetRef]) -> str:
    dataset = datasets.get(layer.dataset_code)
    return f"{layer.title} ({dataset.title})" if dataset is not None else layer.title


def _place(district: DistrictRef) -> str:
    return f"{district.name}, {district.state_name}"
