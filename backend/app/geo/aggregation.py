from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType

from app.core.errors import InvalidInput
from app.geo.records import SeriesTotals
from app.geo.region_rules import region_rules
from app.schemas.region import STATE_AGGREGATIONS

__all__ = [
    "ABSENT_MEANS_ZERO",
    "AGGREGATED_STATS",
    "AGGREGATE_DIGITS",
    "StateAggregate",
    "absent_means_zero",
    "state_aggregate",
]

AGGREGATE_DIGITS = 6
AGGREGATED_STATS = tuple(STATE_AGGREGATIONS)
ABSENT_MEANS_ZERO = MappingProxyType(dict(region_rules().absent_means_zero))


@dataclass(frozen=True)
class StateAggregate:
    aggregation: str
    value: float
    districts: int


def absent_means_zero(dataset_code: str, variable: str) -> bool:
    prefix = ABSENT_MEANS_ZERO.get(dataset_code)
    return prefix is not None and variable.startswith(prefix)


def state_aggregate(totals: SeriesTotals) -> StateAggregate:
    aggregation = STATE_AGGREGATIONS.get(totals.stat)
    if aggregation is None:
        raise InvalidInput(f"{totals.stat} has no state aggregate ({totals.dataset_code}.{totals.variable})")
    districts, area, zeros = totals.districts, totals.area, False
    if absent_means_zero(totals.dataset_code, totals.variable):
        if totals.dataset_districts < totals.districts:
            raise InvalidInput(
                f"state {totals.state_lgd}: {totals.dataset_code} covers fewer districts than hold "
                f"{totals.variable}"
            )
        zeros = totals.dataset_districts > totals.districts
        districts, area = totals.dataset_districts, totals.dataset_area
    return StateAggregate(
        aggregation, round(_aggregate(aggregation, totals, area, zeros), AGGREGATE_DIGITS), districts
    )


def _aggregate(aggregation: str, totals: SeriesTotals, area: float, zeros: bool) -> float:
    if aggregation == "STATE_SUM":
        return totals.total
    if aggregation == "STATE_MIN":
        return min(totals.low, 0.0) if zeros else totals.low
    if aggregation == "STATE_MAX":
        return max(totals.high, 0.0) if zeros else totals.high
    if area <= 0:
        raise InvalidInput(f"state {totals.state_lgd}: {totals.variable} has no district area to weight by")
    return totals.weighted_sum / area
