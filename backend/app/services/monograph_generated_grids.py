from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Claim, Concept
from app.research.monograph_page import TextUnit
from app.research.retrieval import VISIBLE_SENSITIVITY

from .monograph_generated_units import DraftUnit

__all__ = ["FACT_GRID_MIN", "FactGrid", "StatedValue", "fact_grid", "stated_values"]

FACT_GRID_MIN = 2
CONCEPT_SUBJECT = "CONCEPT"
TERM_TAG = "dt"
VALUE_TAG = "dd"
TERM_SUFFIX = "-term"
VALUE_SUFFIX = "-value"


@dataclass(frozen=True)
class StatedValue:
    label: str
    value: Decimal
    unit: str

    def text(self) -> str:
        shown = format(self.value.normalize(), "f")
        return f"{shown} {self.unit}".strip()


@dataclass(frozen=True)
class FactGrid:
    terms: dict[str, TextUnit] = field(default_factory=dict)
    values: tuple[DraftUnit, ...] = ()
    refs: tuple[str, ...] = ()


async def stated_values(
    session: AsyncSession, claim_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, StatedValue]:
    if not claim_ids:
        return {}
    rows = await session.execute(
        select(Claim.id, Concept.name, Claim.valueNum, Claim.valueUnit)
        .join(Concept, and_(Claim.subjectType == CONCEPT_SUBJECT, Concept.id == Claim.subjectId))
        .where(
            Claim.id.in_(list(dict.fromkeys(claim_ids))),
            Claim.valueNum.is_not(None),
            Claim.valueUnit.is_not(None),
            Concept.sensitivity == VISIBLE_SENSITIVITY,
        )
    )
    return {
        claim_id: StatedValue(label=str(name), value=Decimal(value), unit=str(unit))
        for claim_id, name, value, unit in rows.all()
    }


def fact_grid(drafts: Sequence[DraftUnit], values: Mapping[uuid.UUID, StatedValue]) -> FactGrid:
    stated = [(draft, values[claim]) for draft in drafts for claim in draft.claim_ids[:1] if claim in values]
    if len(stated) < FACT_GRID_MIN:
        return FactGrid()
    terms: dict[str, TextUnit] = {}
    cells: list[DraftUnit] = []
    refs: list[str] = []
    for draft, value in stated:
        term_id, value_id = f"{draft.unit_id}{TERM_SUFFIX}", f"{draft.unit_id}{VALUE_SUFFIX}"
        terms[term_id] = TextUnit(
            chapter=draft.chapter, tag=TERM_TAG, field=draft.field, nodes=[value.label], claim_ids=[]
        )
        cells.append(
            DraftUnit(value_id, draft.chapter, draft.field, value.text(), draft.claim_ids[:1], tag=VALUE_TAG)
        )
        refs += [term_id, value_id]
    return FactGrid(terms=terms, values=tuple(cells), refs=tuple(refs))
