import uuid
from typing import Any

import pytest

from app.core.errors import InvalidInput
from app.research.component_specs_general_delivery import (
    DELIVERED_KEY,
    DeliveredComponent,
    DeliveredUnit,
    delivered_claim_ids,
    delivered_of,
    problems_sentence,
    renamed_spec,
    spec_problems,
    unit_problems,
)
from app.research.unit_ids import DELIVERED_UNITS

from .general_spec_fixtures import CHART, TABLE, TIMELINE, chart_units, table_units

FACT = uuid.UUID("5e000000-0000-4000-8000-000000000001")
OTHER = uuid.UUID("5e000000-0000-4000-8000-000000000002")
RAIN = "Bhuj received 518 mm of rain in 1981 and 331 mm in 1982."


def units(raw: dict[str, Any]) -> dict[str, DeliveredUnit]:
    return {ref: DeliveredUnit.model_validate(unit) for ref, unit in raw.items()}


def test_a_chart_whose_units_name_every_place_of_its_spec_has_no_problem() -> None:
    assert spec_problems("chart", CHART, units(chart_units(FACT))) == []
    assert unit_problems(units(chart_units(FACT)), {FACT: [RAIN]}) == []


def test_every_unit_the_spec_names_is_delivered_and_every_unit_has_a_place() -> None:
    delivered = units(chart_units(FACT))
    delivered.pop("u0008")
    delivered["u0099"] = DeliveredUnit(text="A stray line")
    assert spec_problems("chart", CHART, delivered) == [
        "the spec names the unit u0008, which units does not hold",
        "the unit u0099 is in no place of the spec",
    ]


def test_a_value_the_reading_does_not_state_is_a_problem() -> None:
    delivered = units({**chart_units(FACT), "u0006": {"text": "Five hundred mm", "claimIds": [str(FACT)]}})
    assert spec_problems("chart", CHART, delivered) == ["the value 518 is not stated by its unit u0006"]


def test_a_timeline_year_is_stated_by_its_when_unit() -> None:
    cited = [str(FACT)]
    timeline = {
        "u0001": {"text": "Two dates", "claimIds": cited},
        "u0002": {"text": "Two dates", "claimIds": cited},
        "u0003": {"text": "In 1868", "claimIds": cited},
        "u0004": {"text": "Made"},
        "u0005": {"text": "Alizarin was made in a laboratory.", "claimIds": cited},
        "u0006": {"text": "In the year after the war", "claimIds": cited},
        "u0007": {"text": "Freed"},
        "u0008": {"text": "The country became free.", "claimIds": cited},
    }
    assert spec_problems("timeline", TIMELINE, units(timeline)) == [
        "the value 1947 is not stated by its unit u0006"
    ]


def test_a_numeric_column_holds_numbers() -> None:
    numeric = {**TABLE, "columns": [{"label": "u0003"}, {"label": "u0004", "numeric": True}]}
    assert spec_problems("fact_table", numeric, units(table_units(FACT))) == [
        "the unit u0006 sits in a numeric column and states no number"
    ]


def test_a_spec_off_its_model_is_one_problem_naming_where() -> None:
    assert spec_problems("chart", {**CHART, "extra": 1}, units(chart_units(FACT))) == [
        "the chart spec: extra: Extra inputs are not permitted"
    ]
    assert spec_problems("no_such_kind", {}, {}) == ["No spec model draws the component kind 'no_such_kind'"]


def test_a_citation_held_in_the_spec_is_refused_for_one_through_a_unit() -> None:
    cite = {
        "m": "cite",
        "key": "k1",
        "g": ["g1"],
        "shown": [{"number": 1, "title": "A source"}],
        "c": ["1981"],
    }
    figure = {
        "classes": ["fig"],
        "head": {"title": "u0001"},
        "drawing": {"tag": "svg", "attrs": {"viewBox": "0 0 10 10"}},
        "source": {"tag": "p", "text": ["Rain in ", cite]},
    }
    delivered = units({"u0001": {"text": "Rain at Bhuj", "claimIds": [str(FACT)]}})
    assert spec_problems("chart", {"form": "figure", "figure": figure}, delivered) == [
        "a citation in the spec's own text is not allowed: cite a fact through a unit's claimIds"
    ]


def test_a_component_citing_no_fact_is_refused() -> None:
    plain = {ref: {"text": unit["text"]} for ref, unit in chart_units(FACT).items()}
    assert spec_problems("chart", CHART, units(plain)) == [
        "the component cites no fact: at least one unit names the facts it rests on"
    ]


def test_a_unit_cites_shown_facts_and_states_only_their_numbers() -> None:
    delivered = units(
        {
            "u0001": {"text": "Bhuj received 518 mm of rain in 1981.", "claimIds": [str(FACT)]},
            "u0002": {"text": "Bhuj received 620 mm of rain in 1981.", "claimIds": [str(FACT)]},
            "u0003": {"text": "A rain record", "claimIds": [str(OTHER)]},
            "u0004": {
                "text": "A long line that runs on past the length a label may have, so it reads as a sentence"
            },
        }
    )
    assert unit_problems(delivered, {FACT: [RAIN]}) == [
        "the unit u0002 states 620, which none of its facts states",
        f"the unit u0003 cites {OTHER}, which no shown fact has as its id",
        "the unit u0004 is a sentence of more than 80 characters citing no fact",
    ]


def test_a_label_citing_nothing_states_no_number() -> None:
    assert unit_problems(units({"u0001": {"text": "1981"}}), {}) == [
        "the unit u0001 states 1981, which none of its facts states"
    ]


def test_fresh_unit_ids_start_at_5001_and_skip_those_taken() -> None:
    assert DELIVERED_UNITS.fresh(3, {"u5001", "u5003", "overview-ab12"}) == ["u5002", "u5004", "u5005"]
    with pytest.raises(InvalidInput, match="no more room"):
        DELIVERED_UNITS.fresh(4000, {"u5001"})


def test_a_spec_is_renamed_unit_by_unit_and_nothing_else_changes() -> None:
    renamed = renamed_spec(CHART, {"u0005": "u5001", "u0006": "u5002"})
    assert renamed["series"][0]["points"][0] == {"label": "u5001", "value": 518, "reading": "u5002"}
    assert renamed["series"][0]["points"][1] == CHART["series"][0]["points"][1]
    assert renamed["form"] == "bars" and renamed_spec("u0007", {}) == "u0007"


def test_a_stored_delivery_is_read_from_its_payload() -> None:
    raw = {"spec": CHART, "units": chart_units(FACT)}
    found = delivered_of({DELIVERED_KEY: raw, "proposalId": "x"})
    assert isinstance(found, DeliveredComponent) and delivered_claim_ids(found.units) == [FACT]
    assert delivered_of({"monograph": "Kutch-Ajrakh"}) is None


def test_problems_are_joined_into_one_sentence_with_a_count_of_the_rest() -> None:
    assert problems_sentence(["a", "b"]) == "a; b"
    assert problems_sentence([str(n) for n in range(8)]) == "0; 1; 2; 3; 4; 5; and 2 more"


def test_a_unit_names_each_fact_once() -> None:
    with pytest.raises(ValueError, match="each fact it cites once"):
        DeliveredUnit.model_validate({"text": "x", "claimIds": [str(FACT), str(FACT)]})
