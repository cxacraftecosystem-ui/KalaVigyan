import uuid
from typing import Any

from app.research.component_showing import Showing, delivered_showing, piece_showing, same_showing
from app.research.component_specs_general_delivery import DELIVERED_KEY, DeliveredUnit

from .general_spec_fixtures import CHART, chart_units

RAIN_FACT = uuid.UUID("5e000000-0000-4000-8000-0000000000a1")
HEAT_FACT = uuid.UUID("5e000000-0000-4000-8000-0000000000a2")
CLIMATE_FACT = uuid.UUID("5e000000-0000-4000-8000-0000000000a3")
RAIN = "CHIRPS_JAIPUR_ANNUAL_RAIN"
HEAT = "CHELSA_JAIPUR_ANNUAL_HEAT"


def chart(dataset: str | None, column: str, rows: tuple[int, int] = (1, 2)) -> dict[str, Any]:
    points = [
        {**point, "cell": {"row": row, "column": column}}
        for point, row in zip(CHART["series"][0]["points"], rows, strict=True)
    ]
    spec: dict[str, Any] = {**CHART, "series": [{**CHART["series"][0], "points": points}]}
    return spec if dataset is None else {**spec, "dataset": {"code": dataset}}


def units(claim: uuid.UUID) -> dict[str, DeliveredUnit]:
    return {ref: DeliveredUnit.model_validate(unit) for ref, unit in chart_units(claim).items()}


def test_a_component_shows_its_dataset_the_cells_it_draws_and_the_facts_it_cites() -> None:
    shown = delivered_showing("chart", chart(RAIN, "reading"), units(RAIN_FACT))
    assert shown == Showing(
        dataset=RAIN, cells=frozenset({(1, "reading"), (2, "reading")}), facts=frozenset({RAIN_FACT})
    )


def test_two_charts_drawing_the_same_cells_of_one_dataset_show_the_same_thing() -> None:
    first = delivered_showing("chart", chart(RAIN, "reading"), units(RAIN_FACT))
    again = delivered_showing("chart", chart(RAIN, "reading"), units(HEAT_FACT))
    assert same_showing(first, again) == f"it draws 100% of the same cells of the dataset {RAIN}"


def test_one_dataset_drawn_in_another_column_or_other_rows_is_another_figure() -> None:
    rain = delivered_showing("chart", chart(RAIN, "reading"), units(CLIMATE_FACT))
    trend = delivered_showing("chart", chart(RAIN, "trend"), units(CLIMATE_FACT))
    later = delivered_showing("chart", chart(RAIN, "reading", (3, 4)), units(CLIMATE_FACT))
    assert same_showing(rain, trend) is None
    assert same_showing(rain, later) is None


def test_two_figures_of_one_place_from_two_datasets_differ_though_their_captions_cite_one_fact() -> None:
    rain = delivered_showing("chart", chart(RAIN, "reading"), units(CLIMATE_FACT))
    heat = delivered_showing("chart", chart(HEAT, "reading"), units(CLIMATE_FACT))
    assert same_showing(rain, heat) is None


def test_without_a_dataset_the_facts_decide() -> None:
    rain = delivered_showing("chart", chart(None, "reading"), units(RAIN_FACT))
    restated = delivered_showing("chart", chart(None, "reading"), units(RAIN_FACT))
    heat = delivered_showing("chart", chart(None, "reading"), units(HEAT_FACT))
    assert same_showing(rain, restated) == "it rests on the same facts, 100% of them shared"
    assert same_showing(rain, heat) is None


def test_a_figure_drawn_from_a_dataset_is_held_to_the_facts_of_an_authored_one() -> None:
    authored = piece_showing("chart", {"monograph": "Kutch-Ajrakh", "units": []}, [RAIN_FACT])
    assert authored == Showing(dataset=None, cells=frozenset(), facts=frozenset({RAIN_FACT}))
    drawn = delivered_showing("chart", chart(RAIN, "reading"), units(RAIN_FACT))
    other = delivered_showing("chart", chart(RAIN, "reading"), units(HEAT_FACT))
    assert same_showing(drawn, authored) == "it rests on the same facts, 100% of them shared"
    assert same_showing(other, authored) is None


def test_a_registered_piece_shows_what_its_delivered_spec_draws() -> None:
    spec = chart(HEAT, "reading")
    payload = {DELIVERED_KEY: {"spec": spec, "units": chart_units(HEAT_FACT)}}
    assert piece_showing("chart", payload, [HEAT_FACT]) == delivered_showing("chart", spec, units(HEAT_FACT))


def test_a_spec_its_kind_cannot_read_shows_only_its_facts() -> None:
    assert piece_showing("chart", {DELIVERED_KEY: {"spec": {"form": "bars"}, "units": {}}}, [RAIN_FACT]) == (
        Showing(dataset=None, cells=frozenset(), facts=frozenset({RAIN_FACT}))
    )
