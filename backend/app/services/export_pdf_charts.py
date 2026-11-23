from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType

from app.research.blocks_climate import (
    TREND_SIGNIFICANCE,
    TREND_VARIABLES,
    ClimateRiskBlock,
    ClimateSeries,
    ClimateTrend,
    GroundwaterValue,
)
from app.research.blocks_place import MonthlyRain, SeasonRow, SeasonsBlock
from app.research.calendar import MONTH_NAMES, MONTHS
from app.research.calendar_words import SEASON_LABELS

from .export_pdf_styles import (
    CELL,
    CELL_BOLD,
    FIGURE_GAP_MM,
    FIGURE_TITLE,
    KICKER,
    LABEL_COLUMN_MM,
    NOTE,
    cell_height,
)
from .export_pdf_text import measure_text, months_text, p_text, rain_text, sentence_case, years_text
from .pdf_writer import ACCENT, INK, MUTED, RULE, SUNK, Box, PdfWriter, Point, TextStyle

__all__ = [
    "TREND_KEY",
    "TREND_METHOD_TEXT",
    "TREND_WORDS",
    "TrendBar",
    "TrendWords",
    "climate_figure",
    "groundwater_reading",
    "nice_ceiling",
    "rainfall_finding",
    "seasons_figure",
    "significance_text",
    "slope_text",
    "trend_bar",
    "trend_context",
    "trend_finding",
]


@dataclass(frozen=True)
class TrendWords:
    title: str
    noun: str
    lower: str
    higher: str


@dataclass(frozen=True)
class TrendBar:
    left: float
    width: float
    rising: bool


TREND_WORDS: Mapping[str, TrendWords] = MappingProxyType(
    {
        "annual_precipitation": TrendWords("Rainfall trend", "Rainfall", "Drier", "Wetter"),
        "annual_mean_temperature": TrendWords("Temperature trend", "Mean temperature", "Cooler", "Warmer"),
    }
)
TREND_METHOD_TEXT = (
    f"Theil–Sen slope per decade; Mann–Kendall test, significant below p = {TREND_SIGNIFICANCE}"
)
TREND_KEY = "Solid bars are significant; outlined bars are not."
NICE_STEPS = (1.0, 2.0, 2.5, 5.0, 10.0)
GUTTER_MM = 2.0
TRACK_MM = 3.0
ROW_MM = 15.0
SERIES_MM = 28.0
RAIN_BARS_MM = 20.0
CELL_PAD_MM = 0.3
RAIN_VALUE = TextStyle(size=6, colour=MUTED)
ROW_LABEL = TextStyle(size=8.5, bold=True, gap_after=0.5)


def nice_ceiling(value: float) -> float:
    if not math.isfinite(value) or value <= 0:
        return 1.0
    power = 10.0 ** math.floor(math.log10(value))
    return next((step * power for step in NICE_STEPS if step * power >= value), 10 * power)


def trend_bar(slope: float, domain: float) -> TrendBar:
    half = min(1.0, abs(slope) / domain) / 2
    rising = slope >= 0
    return TrendBar(left=0.5 if rising else 0.5 - half, width=half, rising=rising)


def trend_finding(noun: str, trends: Sequence[ClimateTrend]) -> str:
    if len(trends) == 1:
        trend = trends[0]
        if not trend.significant:
            return f"{noun} in {trend.district.name} shows no significant trend"
        change = "risen" if trend.slope_per_decade >= 0 else "fallen"
        shown = measure_text(abs(trend.slope_per_decade), trend.slope_unit)
        return f"{noun} in {trend.district.name} has {change} by {shown}"
    rising = sum(1 for trend in trends if trend.significant and trend.slope_per_decade > 0)
    falling = sum(1 for trend in trends if trend.significant and trend.slope_per_decade < 0)
    total = len(trends)
    if rising == 0 and falling == 0:
        return f"{noun} shows no significant trend in any of the {total} districts"
    if rising >= falling:
        return f"{noun} has risen significantly in {rising} of {total} districts"
    return f"{noun} has fallen significantly in {falling} of {total} districts"


def slope_text(trend: ClimateTrend) -> str:
    shown = measure_text(trend.slope_per_decade, trend.slope_unit)
    return f"+{shown}" if trend.slope_per_decade > 0 else shown


def significance_text(trend: ClimateTrend) -> str:
    return f"{'Significant' if trend.significant else 'Not significant'} · {p_text(trend.p_value)}"


def trend_context(trend: ClimateTrend) -> str:
    mean = f"Mean {measure_text(trend.mean, trend.mean_unit)}"
    return " · ".join((mean, trend.period.replace("-", "–"), trend.resolution))


def groundwater_reading(value: GroundwaterValue) -> str:
    if value.value is not None and value.unit is not None:
        measured = measure_text(value.value, value.unit)
        return f"{value.value_text} · {measured}" if value.value_text else measured
    return value.value_text or ""


def rainfall_finding(rain: MonthlyRain) -> str:
    wettest = max(range(1, MONTHS + 1), key=lambda month: (rain.millimetres[month - 1], -month))
    year = rain_text(sum(rain.millimetres))
    shown = rain_text(rain.millimetres[wettest - 1])
    return (
        f"{MONTH_NAMES[wettest - 1]} is the wettest month in {rain.district.name}: {shown} of a {year} year"
    )


def climate_figure(writer: PdfWriter, block: ClimateRiskBlock) -> None:
    for variable in TREND_VARIABLES:
        trends = [trend for trend in block.trends if trend.variable == variable]
        if trends:
            _trend_chart(writer, TREND_WORDS[variable], trends)
    for series in block.series:
        _series_chart(writer, series)
    if block.groundwater:
        _groundwater(writer, block.groundwater)


def seasons_figure(writer: PdfWriter, block: SeasonsBlock) -> None:
    rain = block.rainfall
    if rain is not None:
        writer.text(rainfall_finding(rain), FIGURE_TITLE)
        _rain_bars(writer, rain)
    if rain is not None or any(row.months for row in block.rows):
        _month_header(writer)
    for row in block.rows:
        _season_row(writer, row)
    writer.go_to(writer.y + FIGURE_GAP_MM)


def _chart_span(writer: PdfWriter) -> tuple[float, float]:
    return writer.left + LABEL_COLUMN_MM + GUTTER_MM, writer.width - LABEL_COLUMN_MM - GUTTER_MM


def _trend_chart(writer: PdfWriter, words: TrendWords, trends: Sequence[ClimateTrend]) -> None:
    writer.text(words.title, KICKER)
    writer.text(trend_finding(words.noun, trends), FIGURE_TITLE)
    writer.text(f"Method: {TREND_METHOD_TEXT}. {TREND_KEY}", NOTE)
    domain = nice_ceiling(max(abs(trend.slope_per_decade) for trend in trends))
    x, width = _chart_span(writer)
    line = cell_height(NOTE)
    axis = Box(x, writer.room(line), width, line)
    writer.label(words.lower, NOTE, axis, align="L")
    writer.label("0", NOTE, axis, align="C")
    writer.label(words.higher, NOTE, axis, align="R")
    writer.go_to(axis.y + line + 1)
    for trend in trends:
        _trend_row(writer, trend, domain)
    writer.go_to(writer.y + FIGURE_GAP_MM)


def _trend_row(writer: PdfWriter, trend: ClimateTrend, domain: float) -> None:
    x, width = _chart_span(writer)
    line = cell_height(CELL)
    top = writer.room(ROW_MM)
    writer.label(trend.district.name, CELL_BOLD, Box(writer.left, top, LABEL_COLUMN_MM, line))
    writer.label(trend.district.state_name, NOTE, Box(writer.left, top + line, LABEL_COLUMN_MM, line))
    track = Box(x, top + 0.5, width, TRACK_MM)
    writer.rect(track, fill=SUNK)
    bar = trend_bar(trend.slope_per_decade, domain)
    shown = Box(x + width * bar.left, track.y, width * bar.width, TRACK_MM)
    writer.rect(shown, fill=ACCENT if trend.significant else None, line=ACCENT, dashed=not trend.significant)
    middle = x + width / 2
    writer.stroke([(middle, track.y - 1), (middle, track.y + TRACK_MM + 1)], INK)
    below = track.y + TRACK_MM + 1.5
    writer.label(f"{slope_text(trend)} · {significance_text(trend)}", CELL_BOLD, Box(x, below, width, line))
    writer.label(trend_context(trend), NOTE, Box(x, below + line, width, line))
    writer.go_to(top + ROW_MM)


def _series_chart(writer: PdfWriter, series: ClimateSeries) -> None:
    readings = [(series.first_year + n, value) for n, value in enumerate(series.values) if value is not None]
    if len(readings) < 2:
        return
    writer.text(f"{TREND_WORDS[series.variable].noun} by year · {series.district.name}", KICKER)
    low, high = min(value for _, value in readings), max(value for _, value in readings)
    top = writer.room(SERIES_MM + cell_height(NOTE))
    frame = Box(writer.left, top, writer.width, SERIES_MM)
    writer.rect(frame, line=RULE)
    last = series.first_year + len(series.values) - 1
    for run in _runs(series):
        writer.stroke(
            [_plotted(frame, (series.first_year, last), (low, high), reading) for reading in run], ACCENT
        )
    writer.go_to(top + SERIES_MM + 1)
    spread = f"lowest {measure_text(low, series.unit)} · highest {measure_text(high, series.unit)}"
    writer.text(f"{years_text(series.first_year, last)} · {spread}", NOTE)


def _runs(series: ClimateSeries) -> list[list[tuple[int, float]]]:
    runs: list[list[tuple[int, float]]] = [[]]
    for n, value in enumerate(series.values):
        if value is None:
            runs.append([])
        else:
            runs[-1].append((series.first_year + n, value))
    return [run for run in runs if len(run) > 1]


def _plotted(
    frame: Box, years: tuple[int, int], values: tuple[float, float], reading: tuple[int, float]
) -> Point:
    (first, last), (low, high), (year, value) = years, values, reading
    across = (year - first) / max(1, last - first)
    up = (value - low) / (high - low) if high > low else 0.5
    return frame.x + frame.width * across, frame.y + frame.height * (1 - up)


def _groundwater(writer: PdfWriter, values: Sequence[GroundwaterValue]) -> None:
    writer.text("Groundwater", KICKER)
    for value in values:
        writer.text(f"{sentence_case(value.variable)} · {value.district.name}", NOTE)
        writer.text(groundwater_reading(value), CELL_BOLD)
        writer.text(f"{value.period} · {value.resolution}", NOTE)
    writer.go_to(writer.y + FIGURE_GAP_MM)


def _rain_bars(writer: PdfWriter, rain: MonthlyRain) -> None:
    x, width = _chart_span(writer)
    cell, line = width / MONTHS, cell_height(RAIN_VALUE)
    top = writer.room(RAIN_BARS_MM + 2 * line)
    writer.label(
        f"Rainfall, {rain.district.name}", CELL_BOLD, Box(writer.left, top, LABEL_COLUMN_MM, line * 2)
    )
    writer.label(rain.period, NOTE, Box(writer.left, top + line * 2, LABEL_COLUMN_MM, line * 2))
    most = max(rain.millimetres)
    for month, value in enumerate(rain.millimetres, 1):
        height = RAIN_BARS_MM * (value / most if most > 0 else 0)
        left = x + (month - 1) * cell
        writer.rect(
            Box(left + CELL_PAD_MM, top + RAIN_BARS_MM - height, cell - 2 * CELL_PAD_MM, height), fill=ACCENT
        )
        writer.label(rain_text(value), RAIN_VALUE, Box(left, top + RAIN_BARS_MM + 0.5, cell, line), align="C")
    writer.go_to(top + RAIN_BARS_MM + line + 1.5)


def _month_header(writer: PdfWriter) -> None:
    x, width = _chart_span(writer)
    cell, line = width / MONTHS, cell_height(NOTE)
    top = writer.room(line)
    for month in range(1, MONTHS + 1):
        writer.label(MONTH_NAMES[month - 1][0], NOTE, Box(x + (month - 1) * cell, top, cell, line), align="C")
    writer.go_to(top + line + 0.5)


def _season_row(writer: PdfWriter, row: SeasonRow) -> None:
    x, width = _chart_span(writer)
    line = cell_height(CELL)
    top = writer.room(2 * line + 1)
    writer.text(row.label, ROW_LABEL, width=LABEL_COLUMN_MM)
    label_bottom = writer.y
    if row.months:
        cell, named = width / MONTHS, set(row.months)
        for month in range(1, MONTHS + 1):
            box = Box(x + (month - 1) * cell + CELL_PAD_MM, top + 0.6, cell - 2 * CELL_PAD_MM, TRACK_MM)
            writer.rect(box, fill=ACCENT if month in named else SUNK)
        writer.label(months_text(row.months), NOTE, Box(x, top + line, width, line))
    if row.season is not None:
        season_y = top + 2 * line if row.months else top
        writer.label(SEASON_LABELS[row.season], CELL, Box(x, season_y, width, line))
    lines = 1 + (1 if row.months else 0) + (1 if row.months and row.season else 0)
    writer.go_to(max(label_bottom, top + lines * line + 1))
