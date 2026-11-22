from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Collection, Mapping, Sequence

from pydantic import ValidationError

from app.models.enums import DISCIPLINES
from app.research.blocks_insight import (
    MEASURE_ROWS_MAX,
    MeasureBlock,
    MeasureRow,
    MetricAmount,
    UnitConversion,
)
from app.research.crafts import CraftRef
from app.research.local_units import LOCAL_UNITS
from app.research.measures import DEFINED_UNITS, UNIT_DEFINITIONS, metric_value
from app.research.stated_quantities import StatedQuantity, stated_quantities
from app.science.records import KnownClaim

from .builder_evidence import fact_sentence, section_facts, sources_beyond
from .builder_interface import BuildAsk, BuilderTools, Built
from .measure_regions import RegionalFactor, RegionalFactors
from .measure_store import regional_factors

__all__ = ["MEASURE_FIELDS", "FactorLoader", "MeasureBuilder", "measure_block", "stated_in"]

logger = logging.getLogger(__name__)

MEASURE_FIELDS = frozenset(DISCIPLINES)

FactorLoader = Callable[[CraftRef, Collection[str]], Awaitable[RegionalFactors]]
Stated = tuple[KnownClaim, StatedQuantity]


class MeasureBuilder:
    def __init__(self, tools: BuilderTools, *, factors: FactorLoader | None = None) -> None:
        self._factors = factors or _stored_factors(tools)

    async def build(self, ask: BuildAsk) -> Built:
        found = stated_in(section_facts(ask.blocks, ask.cited))
        if not found:
            return Built()
        local = frozenset(quantity.unit for _, quantity in found if quantity.unit in LOCAL_UNITS)
        craft = ask.request.craft
        regional = await self._factors(craft, local) if local and craft is not None else RegionalFactors()
        block = measure_block(found, regional.factors, block_id=f"{ask.section.id}.measure")
        if block is None:
            return Built()
        return Built((block,), sources_beyond([block], regional.sources, ask.cited))


def stated_in(facts: Sequence[KnownClaim]) -> list[Stated]:
    return [(fact, quantity) for fact in facts for quantity in stated_quantities(fact.text)]


def measure_block(
    found: Sequence[Stated], factors: Mapping[str, RegionalFactor], *, block_id: str
) -> MeasureBlock | None:
    rows: list[MeasureRow] = []
    for fact, quantity in found:
        conversion = _conversion(quantity.unit, factors)
        row = None if conversion is None else _row(fact, quantity, conversion, f"{block_id}.{len(rows) + 1}")
        if row is not None:
            rows.append(row)
        if len(rows) == MEASURE_ROWS_MAX:
            break
    if not rows:
        return None
    try:
        return MeasureBlock(id=block_id, kind="measure", version=1, reuse=None, rows=rows)
    except ValidationError as refused:
        logger.warning("the measure block %s is not shown: %s", block_id, refused)
        return None


def _conversion(unit: str, factors: Mapping[str, RegionalFactor]) -> UnitConversion | None:
    defined = DEFINED_UNITS.get(unit)
    regional = factors.get(unit)
    try:
        if defined is not None:
            return UnitConversion(
                unit=unit,
                metric_unit=defined.metric_unit,
                factor=float(defined.factor),
                basis="DEFINED",
                region=None,
                citation=None,
                dataset=UNIT_DEFINITIONS,
            )
        if regional is None:
            return None
        return UnitConversion(
            unit=unit,
            metric_unit=regional.metric_unit,
            factor=float(regional.factor),
            basis="REGIONAL",
            region=regional.region,
            citation=regional.citation,
            dataset=None,
        )
    except ValidationError as refused:
        logger.info("a %s conversion is refused: %s", unit, refused)
        return None


def _row(
    fact: KnownClaim, quantity: StatedQuantity, conversion: UnitConversion, sentence_id: str
) -> MeasureRow | None:
    low = float(quantity.low)
    high = None if quantity.high is None else float(quantity.high)
    try:
        return MeasureRow(
            stated=quantity.stated,
            low=low,
            high=high,
            unit_label=quantity.unit_label,
            conversion=conversion,
            metric=MetricAmount(
                low=metric_value(low, conversion.factor),
                high=None if high is None else metric_value(high, conversion.factor),
                unit=conversion.metric_unit,
            ),
            sentence=fact_sentence(fact, sentence_id),
        )
    except ValidationError as refused:
        logger.info("the measure %r is not shown: %s", quantity.stated, refused)
        return None


def _stored_factors(tools: BuilderTools) -> FactorLoader:
    async def load(craft: CraftRef, units: Collection[str]) -> RegionalFactors:
        async with tools.sessions() as session:
            return await regional_factors(session, craft.slug, units)

    return load
