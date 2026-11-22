import math

import pytest

from app.research.blocks_climate import ClimateRiskBlock
from app.research.blocks_insight import MeasureBlock, MeasureRegion
from app.research.blocks_play import SimulationValue
from app.services.export_pdf_charts import (
    nice_ceiling,
    rainfall_finding,
    slope_text,
    trend_bar,
    trend_context,
    trend_finding,
)
from app.services.export_pdf_figures import measure_basis, measure_line, simulation_value_text
from app.services.export_pdf_maps import district_names, district_outlines, map_projection
from app.services.export_pdf_text import (
    compound_text,
    measure_text,
    months_text,
    number_text,
    p_text,
    rain_text,
    range_text,
    years_text,
)

from ..contracts.phase_d_golden import phase_d_blocks
from .figure_fixtures import kachchh_rain

GUJARAT_LGD = 24
GUJARAT_DISTRICTS = 33
KACHCHH_LGD = 449


def golden_trend() -> ClimateRiskBlock:
    return ClimateRiskBlock.model_validate(phase_d_blocks()["s6.b1"])


@pytest.mark.parametrize(
    ("value", "expected"),
    [(1234567.891, "12,34,567.89"), (449.356389, "449.36"), (10.0, "10"), (3.1, "3.1"), (-0.5, "−0.5")],
)
def test_numbers_are_written_as_the_screen_writes_them(value: float, expected: str) -> None:
    assert number_text(value) == expected


@pytest.mark.parametrize(
    ("p_value", "expected"), [(0.004992, "p = 0.005"), (0.0004, "p < 0.001"), (0.2345, "p = 0.23")]
)
def test_a_p_value_is_written_to_its_precision(p_value: float, expected: str) -> None:
    assert p_text(p_value) == expected


def test_units_ranges_months_years_and_rain_are_written_as_on_screen() -> None:
    assert measure_text(70.760167, "mm/year per decade") == "70.76 mm/year per decade"
    assert measure_text(1.5, "degC per decade") == "1.5 °C per decade"
    assert measure_text(0.25, "fraction") == "25%"
    assert range_text(3.05, 4.57, "m") == "3.05–4.57 m"
    assert range_text(3.0, 3.0, "m") == "3 m"
    assert months_text([6, 7, 8, 9]) == "June–September"
    assert months_text([1, 3, 4]) == "January, March–April"
    assert years_text(1586, 1631) == "1586–1631" and years_text(2001, 2001) == "2001"
    assert rain_text(123.4) == "123 mm" and rain_text(4.26) == "4.3 mm"
    assert compound_text("Alizarin", "C14H8O4", 6293) == "Alizarin · C14H8O4 · PubChem CID 6293"
    assert compound_text("Alum", None, None) == "Alum"


def test_a_trend_scale_rounds_up_to_a_nice_step() -> None:
    assert nice_ceiling(70.760167) == 100.0
    assert nice_ceiling(0.3) == pytest.approx(0.5)
    assert nice_ceiling(0.0) == 1.0


def test_a_trend_bar_starts_at_zero_and_reaches_half_the_track_at_the_scale() -> None:
    rising = trend_bar(70.760167, 100.0)
    assert rising.rising and rising.left == 0.5 and rising.width == pytest.approx(0.35380083)
    falling = trend_bar(-30.0, 100.0)
    assert not falling.rising and falling.left == pytest.approx(0.35) and falling.width == pytest.approx(0.15)
    assert trend_bar(250.0, 100.0).width == 0.5


def test_the_golden_trend_is_written_with_its_slope_mean_and_finding() -> None:
    trend = golden_trend().trends[0]
    assert slope_text(trend) == "+70.76 mm/year per decade"
    assert trend_context(trend) == "Mean 449.36 mm/year · 1981–2025 · 0.05 degree"
    assert trend_finding("Rainfall", [trend]) == "Rainfall in Kachchh has risen by 70.76 mm/year per decade"
    flat = trend.model_copy(update={"significant": False, "p_value": 0.4})
    assert trend_finding("Rainfall", [flat]) == "Rainfall in Kachchh shows no significant trend"
    assert trend_finding("Rainfall", [trend, flat]) == "Rainfall has risen significantly in 1 of 2 districts"


def test_the_wettest_month_is_the_first_largest() -> None:
    assert rainfall_finding(kachchh_rain()) == "July is the wettest month in Kachchh: 150 mm of a 394 mm year"


def test_a_measure_is_written_stated_then_metric_with_its_basis() -> None:
    row = MeasureBlock.model_validate(phase_d_blocks()["s4.b1"]).rows[0]
    assert measure_line(row) == "10-15 feet is 3.05–4.57 m"
    assert measure_basis(row) == "Exact definition"
    region = MeasureRegion(
        state_lgd=GUJARAT_LGD, state_name="Gujarat", district_lgd=KACHCHH_LGD, district_name="Kachchh"
    )
    regional = row.conversion.model_copy(update={"basis": "REGIONAL", "region": region})
    assert measure_basis(row.model_copy(update={"conversion": regional})) == "As stated for Kachchh, Gujarat"


def test_a_generated_explainer_value_is_written_as_stated_or_with_its_unit() -> None:
    stated = SimulationValue.model_construct(
        label="Yearly fall", value=10.0, unit="feet a year", stated="10-15 feet"
    )
    assert simulation_value_text(stated) == "Yearly fall: 10-15 feet"
    measured = stated.model_copy(update={"stated": None, "unit": "degC"})
    assert simulation_value_text(measured) == "Yearly fall: 10 °C"


def test_a_district_is_filled_over_the_outlines_of_its_state() -> None:
    outlines = district_outlines([KACHCHH_LGD])
    assert [shape.lgd for shape in outlines.filled] == [KACHCHH_LGD]
    assert {shape.state_lgd for shape in outlines.context} == {GUJARAT_LGD}
    assert len(outlines.context) == GUJARAT_DISTRICTS
    assert district_names([KACHCHH_LGD]) == ["Kachchh, Gujarat"]


def test_a_district_without_a_shape_draws_no_outline() -> None:
    outlines = district_outlines([999_999])
    assert outlines.filled == () and outlines.context == ()
    assert map_projection(outlines.points(), 100.0, 100.0) is None


def test_the_projection_squeezes_longitude_by_the_middle_latitude_and_fits_the_frame() -> None:
    projection = map_projection([(70.0, 24.0), (72.0, 22.0)], 100.0, 100.0)
    assert projection is not None
    squeeze = math.cos(math.radians(23.0))
    assert projection.scale == pytest.approx(50.0)
    assert projection.width == pytest.approx(2 * squeeze * 50.0) and projection.height == pytest.approx(100.0)
    assert projection.place((70.0, 24.0)) == pytest.approx((0.0, 0.0))
    assert projection.place((72.0, 22.0)) == pytest.approx((2 * squeeze * 50.0, 100.0))


def test_gujarat_fits_the_report_s_map_frame() -> None:
    outlines = district_outlines([KACHCHH_LGD])
    projection = map_projection(outlines.points(), 178.0, 75.0)
    assert projection is not None
    assert projection.width <= 178.0 + 1e-6 and projection.height <= 75.0 + 1e-6
    assert math.isclose(projection.width, 178.0) or math.isclose(projection.height, 75.0)
    placed = [projection.place(point) for point in outlines.points()]
    assert all(-1e-6 <= x <= projection.width + 1e-6 for x, _ in placed)
    assert all(-1e-6 <= y <= projection.height + 1e-6 for _, y in placed)
