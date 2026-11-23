import math
from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

from geo_etl.rows import Rows

TREND_YEARS_MIN = 30
TREND_SIGNIFICANCE = 0.05
DECADE_YEARS = 10
SLOPE_STAT = "TREND_PER_DECADE"
P_VALUE_STAT = "TREND_P_VALUE"
P_VALUE_UNIT = "p-value"
TREND_UNITS = {
    "annual_precipitation": ("mm/year", "mm/year per decade"),
    "annual_mean_temperature": ("degC", "degC per decade"),
}
TREND_METHOD = (
    "Theil-Sen slope (median of the slopes between every pair of years) of the yearly district means, "
    "times ten for a decade; two-sided Mann-Kendall test, normal approximation with the tie-corrected "
    "variance and continuity correction; written only for a complete series of at least 30 years"
)


@dataclass(frozen=True)
class Trend:
    slope_per_year: float
    p_value: float

    @property
    def slope_per_decade(self) -> float:
        return self.slope_per_year * DECADE_YEARS


@dataclass(frozen=True)
class AnnualSeries:
    variable: str
    first_year: int
    values: tuple[float, ...]

    @property
    def period(self) -> str:
        return f"{self.first_year}-{self.first_year + len(self.values) - 1}"

    @property
    def complete(self) -> bool:
        return bool(self.values) and all(math.isfinite(value) for value in self.values)


def sen_slope(values: Sequence[float]) -> float:
    series = np.asarray(values, dtype="float64")
    first, second = np.triu_indices(len(series), k=1)
    if not len(first):
        raise ValueError("a slope needs at least two years")
    return float(np.median((series[second] - series[first]) / (second - first)))


def mann_kendall_p(values: Sequence[float]) -> float:
    series = np.asarray(values, dtype="float64")
    count = len(series)
    first, second = np.triu_indices(count, k=1)
    score = float(np.sign(series[second] - series[first]).sum())
    _, ties = np.unique(series, return_counts=True)
    tied = float((ties * (ties - 1) * (2 * ties + 5)).sum())
    variance = (count * (count - 1) * (2 * count + 5) - tied) / 18.0
    if score == 0 or variance <= 0:
        return 1.0
    z = (score - math.copysign(1.0, score)) / math.sqrt(variance)
    return math.erfc(abs(z) / math.sqrt(2.0))


def series_trend(series: AnnualSeries) -> Trend | None:
    if not series.complete or len(series.values) < TREND_YEARS_MIN:
        return None
    return Trend(slope_per_year=sen_slope(series.values), p_value=mann_kendall_p(series.values))


def add_trend_rows(rows: Rows, district: pd.Series, series: AnnualSeries) -> None:
    trend = series_trend(series)
    if trend is None:
        return
    variable, period = series.variable, series.period
    slope_unit = TREND_UNITS[variable][1]
    rows.add(district, variable, period, SLOPE_STAT, trend.slope_per_decade, unit=slope_unit, method=TREND_METHOD)
    rows.add(district, variable, period, P_VALUE_STAT, trend.p_value, unit=P_VALUE_UNIT, method=TREND_METHOD)
