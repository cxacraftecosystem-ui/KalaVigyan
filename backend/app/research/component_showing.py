from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.core.errors import InvalidInput

from .component_specs import checked_spec
from .component_specs_general_delivery import (
    DeliveredUnit,
    cited_cells,
    cited_dataset,
    delivered_claim_ids,
    delivered_of,
)

__all__ = [
    "CLOSE_CELL_OVERLAP",
    "CLOSE_FACT_OVERLAP",
    "Showing",
    "delivered_showing",
    "piece_showing",
    "same_showing",
]

CLOSE_CELL_OVERLAP = 0.8
CLOSE_FACT_OVERLAP = 0.8
SAME_CELLS = "it draws {share:.0%} of the same cells of the dataset {code}"
SAME_DATASET = "it draws from the same dataset {code}"
SAME_FACTS = "it rests on the same facts, {share:.0%} of them shared"

Cell = tuple[int, str]


@dataclass(frozen=True)
class Showing:
    dataset: str | None
    cells: frozenset[Cell]
    facts: frozenset[uuid.UUID]


def delivered_showing(kind: str, spec: Mapping[str, Any], units: Mapping[str, DeliveredUnit]) -> Showing:
    dataset, cells = _data(kind, spec)
    return Showing(dataset=dataset, cells=cells, facts=frozenset(delivered_claim_ids(units)))


def piece_showing(kind: str, payload: Mapping[str, Any], claim_ids: Iterable[uuid.UUID]) -> Showing:
    delivered = delivered_of(payload)
    dataset, cells = (None, frozenset()) if delivered is None else _data(kind, delivered.spec)
    return Showing(dataset=dataset, cells=cells, facts=frozenset(claim_ids))


def same_showing(first: Showing, second: Showing) -> str | None:
    if first.dataset is not None and second.dataset is not None:
        return _same_data(first, second)
    share = _overlap(first.facts, second.facts)
    if first.facts and second.facts and share >= CLOSE_FACT_OVERLAP:
        return SAME_FACTS.format(share=share)
    return None


def _same_data(first: Showing, second: Showing) -> str | None:
    if first.dataset != second.dataset:
        return None
    if not first.cells and not second.cells:
        return SAME_DATASET.format(code=first.dataset)
    share = _overlap(first.cells, second.cells)
    return SAME_CELLS.format(share=share, code=first.dataset) if share >= CLOSE_CELL_OVERLAP else None


def _data(kind: str, spec: Mapping[str, Any]) -> tuple[str | None, frozenset[Cell]]:
    try:
        checked = checked_spec(kind, spec)
    except ValidationError, InvalidInput:
        return None, frozenset()
    dataset = cited_dataset(checked)
    cells = frozenset((cited.cell.row, cited.cell.column) for cited in cited_cells(checked))
    return (None if dataset is None else dataset.code), cells


def _overlap[Item](first: frozenset[Item], second: frozenset[Item]) -> float:
    union = first | second
    return len(first & second) / len(union) if union else 0.0
