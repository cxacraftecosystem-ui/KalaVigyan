from __future__ import annotations

import logging
from collections.abc import Sequence

from pydantic import ValidationError

from app.models.enums import DISCIPLINES
from app.research.blocks_insight import QUANTITY_ROWS_MAX, QUANTITY_ROWS_MIN, QuantitiesBlock, QuantityRow
from app.research.stated_amounts import StatedAmount, stated_amounts
from app.science.records import KnownClaim

from .builder_evidence import fact_sentence, section_facts
from .builder_interface import BuildAsk, BuilderTools, Built

__all__ = ["QUANTITY_FIELDS", "QuantitiesBuilder", "amounts_stated_in", "quantities_block"]

logger = logging.getLogger(__name__)

QUANTITY_FIELDS = frozenset(DISCIPLINES)
BLOCK_SUFFIX = "quantities"

Stated = tuple[KnownClaim, StatedAmount]


class QuantitiesBuilder:
    def __init__(self, tools: BuilderTools) -> None:
        self._tools = tools

    async def build(self, ask: BuildAsk) -> Built:
        found = amounts_stated_in(section_facts(ask.blocks, ask.cited))
        block = quantities_block(found, block_id=f"{ask.section.id}.{BLOCK_SUFFIX}")
        return Built((block,)) if block is not None else Built()


def amounts_stated_in(facts: Sequence[KnownClaim]) -> list[Stated]:
    return [(fact, amount) for fact in facts for amount in stated_amounts(fact.text)]


def quantities_block(found: Sequence[Stated], *, block_id: str) -> QuantitiesBlock | None:
    rows: list[QuantityRow] = []
    for fact, amount in found:
        row = _row(fact, amount, f"{block_id}.{len(rows) + 1}")
        if row is not None:
            rows.append(row)
        if len(rows) == QUANTITY_ROWS_MAX:
            break
    if len(rows) < QUANTITY_ROWS_MIN:
        return None
    try:
        return QuantitiesBlock(id=block_id, kind="quantities", version=1, reuse=None, rows=rows)
    except ValidationError as refused:
        logger.warning("the quantities %s are not shown: %s", block_id, refused)
        return None


def _row(fact: KnownClaim, amount: StatedAmount, sentence_id: str) -> QuantityRow | None:
    try:
        return QuantityRow(
            stated=amount.stated,
            low=float(amount.low),
            high=None if amount.high is None else float(amount.high),
            unit=amount.unit,
            measures=amount.measures,
            sentence=fact_sentence(fact, sentence_id),
        )
    except ValidationError as refused:
        logger.info("the quantity %r is not shown: %s", amount.stated, refused)
        return None
