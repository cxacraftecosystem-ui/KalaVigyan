from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Annotated, Any, Self

from pydantic import Field, ValidationError, model_validator

from app.core.errors import InvalidInput

from .base import ContractModel
from .component_specs import checked_spec, not_contributable
from .component_specs_general import (
    GENERAL_CHART,
    GENERAL_MAP_LAYER,
    GENERAL_TABLE,
    GENERAL_TIMELINE,
    DataCell,
    DatasetCite,
    GeneralChartSpec,
    GeneralMapLayerSpec,
    GeneralTableSpec,
    GeneralTimelineSpec,
)
from .component_specs_tools import spec_unit_refs
from .drawing_spec_rules import THEMES_KEY, spec_design_problems
from .quotes import numbers_in, unsupported_figures
from .unit_ids import UNIT_REF, UNIT_REF_PATTERN

__all__ = [
    "CLAIMS_PER_UNIT_MAX",
    "CONTAINER_KINDS",
    "DELIVERED_KEY",
    "LABEL_MAX_CHARS",
    "UNITS_MAX",
    "CitedCell",
    "DeliveredComponent",
    "DeliveredUnit",
    "UnitKey",
    "cited_cells",
    "cited_dataset",
    "delivered_claim_ids",
    "delivered_of",
    "problems_sentence",
    "renamed_spec",
    "spec_problems",
    "unit_problems",
]

UNITS_MAX = 400
UNIT_TEXT_MAX = 600
LABEL_MAX_CHARS = 80
CLAIMS_PER_UNIT_MAX = 20
CITE_MARK = "cite"
DELIVERED_KEY = "delivered"
PROBLEMS_SHOWN = 6
THEMES_SENT = "the server draws a drawing in each of the four themes from its svg, so a spec sends no themes"

UnitKey = Annotated[str, Field(pattern=UNIT_REF_PATTERN)]
NO_ROWS: Mapping[str, Sequence[str]] = MappingProxyType({})
CONTAINER_KINDS = frozenset({"experiment_lab"})


class DeliveredUnit(ContractModel):
    text: str = Field(min_length=1, max_length=UNIT_TEXT_MAX)
    claim_ids: list[uuid.UUID] = Field(default_factory=list, max_length=CLAIMS_PER_UNIT_MAX)

    @model_validator(mode="after")
    def _each_once(self) -> Self:
        if len(set(self.claim_ids)) != len(self.claim_ids):
            raise ValueError("a unit names each fact it cites once")
        return self


class DeliveredComponent(ContractModel):
    spec: dict[str, Any]
    units: dict[UnitKey, DeliveredUnit] = Field(default_factory=dict, max_length=UNITS_MAX)


def delivered_of(payload: Mapping[str, Any]) -> DeliveredComponent | None:
    raw = payload.get(DELIVERED_KEY)
    return None if raw is None else DeliveredComponent.model_validate(raw)


def delivered_claim_ids(units: Mapping[str, DeliveredUnit]) -> list[uuid.UUID]:
    return list(dict.fromkeys(claim for unit in units.values() for claim in unit.claim_ids))


def spec_problems(kind: str, spec: Mapping[str, Any], units: Mapping[str, DeliveredUnit]) -> list[str]:
    refused = not_contributable(kind)
    if refused is not None:
        return [refused]
    try:
        checked = checked_spec(kind, spec)
    except ValidationError as wrong:
        return [f"the {kind} spec: {_first(wrong)}"]
    except InvalidInput as wrong:
        return [str(wrong)]
    named = set(spec_unit_refs(checked))
    problems = [
        f"the spec names the unit {ref}, which units does not hold" for ref in sorted(named - set(units))
    ]
    problems += [f"the unit {ref} is in no place of the spec" for ref in sorted(set(units) - named)]
    if _held_citations(checked.model_dump(mode="json")):
        problems.append(
            "a citation in the spec's own text is not allowed: cite a fact through a unit's claimIds"
        )
    if not delivered_claim_ids(units) and cited_dataset(checked) is None and kind not in CONTAINER_KINDS:
        problems.append("the component cites no fact: at least one unit names the facts it rests on")
    if THEMES_KEY in spec:
        problems.append(THEMES_SENT)
    problems += spec_design_problems(checked.model_dump(mode="json"))
    return problems + _value_problems(kind, checked, units)


def unit_problems(
    units: Mapping[str, DeliveredUnit],
    cited: Mapping[uuid.UUID, Sequence[str]],
    rows: Mapping[str, Sequence[str]] = NO_ROWS,
) -> list[str]:
    problems: list[str] = []
    for ref, unit in sorted(units.items()):
        missing = [str(claim) for claim in unit.claim_ids if claim not in cited]
        if missing:
            problems.append(f"the unit {ref} cites {', '.join(missing)}, which no shown fact has as its id")
            continue
        if not unit.claim_ids and ref not in rows and len(unit.text) > LABEL_MAX_CHARS:
            problems.append(
                f"the unit {ref} is a sentence of more than {LABEL_MAX_CHARS} characters citing no fact"
            )
        stated = [*(text for claim in unit.claim_ids for text in cited[claim]), *rows.get(ref, ())]
        figures = unsupported_figures(unit.text, stated)
        if figures:
            problems.append(f"the unit {ref} states {', '.join(figures)}, which none of its facts states")
    return problems


def problems_sentence(problems: Sequence[str]) -> str:
    shown = "; ".join(problems[:PROBLEMS_SHOWN])
    more = len(problems) - PROBLEMS_SHOWN
    return f"{shown}; and {more} more" if more > 0 else shown


def renamed_spec(value: Any, names: Mapping[str, str]) -> Any:
    if isinstance(value, str):
        return names.get(value, value) if UNIT_REF.match(value) else value
    if isinstance(value, list):
        return [renamed_spec(item, names) for item in value]
    if isinstance(value, dict):
        return {key: renamed_spec(item, names) for key, item in value.items()}
    return value


def _value_problems(kind: str, spec: Any, units: Mapping[str, DeliveredUnit]) -> list[str]:
    if kind == GENERAL_TABLE and isinstance(spec, GeneralTableSpec):
        return _table_problems(spec, units)
    return [
        f"the value {value:g} is not stated by its unit {ref}"
        for value, ref in _stated_values(kind, spec)
        if ref in units and not any(_same(value, figure) for figure in numbers_in(units[ref].text))
    ]


def _stated_values(kind: str, spec: Any) -> list[tuple[float, str]]:
    if kind == GENERAL_CHART and isinstance(spec, GeneralChartSpec):
        return [(point.value, point.reading) for series in spec.series for point in series.points]
    if kind == GENERAL_TIMELINE and isinstance(spec, GeneralTimelineSpec):
        return [(float(abs(event.year)), event.when) for event in spec.events]
    if kind == GENERAL_MAP_LAYER and isinstance(spec, GeneralMapLayerSpec):
        return [(place.value, place.reading) for place in spec.places if place.value is not None]
    return []


def _table_problems(spec: GeneralTableSpec, units: Mapping[str, DeliveredUnit]) -> list[str]:
    numeric = [at for at, column in enumerate(spec.columns) if column.numeric]
    return [
        f"the unit {row.cells[at]} sits in a numeric column and states no number"
        for row in spec.rows
        for at in numeric
        if row.cells[at] in units and not numbers_in(units[row.cells[at]].text)
    ]


def _same(value: float, figure: str) -> bool:
    try:
        return float(figure) == value
    except ValueError:
        return False


def _held_citations(value: Any) -> bool:
    if isinstance(value, dict):
        return value.get("m") == CITE_MARK or any(_held_citations(item) for item in value.values())
    if isinstance(value, list):
        return any(_held_citations(item) for item in value)
    return False


def _first(wrong: ValidationError) -> str:
    problem = wrong.errors()[0]
    where = ".".join(str(part) for part in problem["loc"])
    return f"{where}: {problem['msg']}" if where else str(problem["msg"])


@dataclass(frozen=True)
class CitedCell:
    cell: DataCell
    unit: str
    value: float | None


def cited_dataset(spec: Any) -> DatasetCite | None:
    if isinstance(spec, GeneralChartSpec | GeneralTableSpec | GeneralMapLayerSpec):
        return spec.dataset
    return None


def cited_cells(spec: Any) -> list[CitedCell]:
    if isinstance(spec, GeneralChartSpec):
        points = [point for series in spec.series for point in series.points]
        return [
            CitedCell(point.cell, point.reading, point.value) for point in points if point.cell is not None
        ]
    if isinstance(spec, GeneralMapLayerSpec):
        return [
            CitedCell(place.cell, place.reading, place.value)
            for place in spec.places
            if place.cell is not None
        ]
    if isinstance(spec, GeneralTableSpec):
        return [
            CitedCell(DataCell(row=row.row, column=column.column), row.cells[at], None)
            for row in spec.rows
            if row.row is not None
            for at, column in enumerate(spec.columns)
            if column.column is not None
        ]
    return []
