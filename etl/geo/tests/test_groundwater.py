import json

import pytest
import requests

from geo_etl.catalog import GROUNDWATER
from geo_etl.coverage import coverage_of
from geo_etl.districts import load_districts, load_register
from geo_etl.layers import Options, groundwater
from geo_etl.rows import COLUMNS

KEY = "fixture-key-not-a-real-one"
API = "https://api.data.gov.in/resource/1dc76140-9468-4507-a1a2-2abb19e79782"
AJMER, CHITTORGARH, JHUNJHUNU, KACHCHH = 86, 95, 106, 449
RAJASTHAN = 8
FIELD_LIST = [
    {"id": "sl__no_", "name": "Sl. No.", "type": "keyword"},
    {"id": "name_of_district", "name": "Name of District", "type": "keyword"},
    {"id": "total_annual_ground_water_recharge", "name": "Total Annual Ground Water Recharge", "type": "double"},
    {
        "id": "annual_extractable_ground_water_resource",
        "name": "Annual Extractable Ground Water Resource",
        "type": "double",
    },
    {
        "id": "current_annual_ground_water_extraction___irrigation",
        "name": "Current Annual Ground Water Extraction - Irrigation",
        "type": "double",
    },
    {
        "id": "current_annual_ground_water_extraction___industrial",
        "name": "Current Annual Ground Water Extraction - Industrial",
        "type": "double",
    },
    {
        "id": "current_annual_ground_water_extraction___domestic",
        "name": "Current Annual Ground Water Extraction - Domestic",
        "type": "double",
    },
    {
        "id": "current_annual_ground_water_extraction___total",
        "name": "Current Annual Ground Water Extraction - Total",
        "type": "double",
    },
    {"id": "stage_of_ground_water_extraction____", "name": "Stage of Ground Water Extraction (%)", "type": "double"},
]


def table_row(number: str, name: str, *figures: float) -> dict:
    ids = [item["id"] for item in FIELD_LIST[2:]]
    return {"sl__no_": number, "name_of_district": name} | dict(zip(ids, figures, strict=True))


AJMER_ROW = table_row("1", "Ajmer", 37959.01, 34163.11, 47462.83, 176, 1184.34, 48823.19, 142.91)
CHITTAURGARH_ROW = table_row("10", "Chittaurgarh", 34553.28, 31097.97, 46512.33, 107.23, 2028.21, 48647.78, 156.43)
JHUNJHUNUN_ROW = table_row("21", "Jhunjhunun", 24551.09, 22095.98, 35396.64, 564.16, 11912.02, 47872.82, 216.66)
TOTAL_ROW = table_row("Total", "Total", 1245198.96, 1125135.44, 1430424.28, 12777.86, 230704.79, 1673907.14, 148.77)
AJMER_VALUES = {
    "annual_groundwater_recharge": ("TOTAL", 37959.01, "ham"),
    "annual_extractable_groundwater": ("TOTAL", 34163.11, "ham"),
    "annual_groundwater_extraction_irrigation": ("TOTAL", 47462.83, "ham"),
    "annual_groundwater_extraction_industrial": ("TOTAL", 176.0, "ham"),
    "annual_groundwater_extraction_domestic": ("TOTAL", 1184.34, "ham"),
    "annual_groundwater_extraction": ("TOTAL", 48823.19, "ham"),
    "stage_of_groundwater_extraction": ("SHARE", 142.91, "%"),
}


def answer(status: int, body: object) -> requests.Response:
    made = requests.Response()
    made.status_code = status
    made._content = json.dumps(body).encode("utf-8")
    return made


def page(records: list[dict], *, total: int, offset: int, fields: list[dict] = FIELD_LIST) -> requests.Response:
    body = {"status": "ok", "total": total, "count": len(records), "offset": str(offset), "field": fields}
    return answer(200, body | {"records": records})


class Portal:
    def __init__(self, answers: tuple):
        self.answers = list(answers)
        self.calls: list[dict] = []

    def __call__(self, method, url, *, params, headers, timeout):
        self.calls.append({"method": method, "url": url, "agent": headers["User-Agent"]} | params)
        step = self.answers.pop(0) if len(self.answers) > 1 else self.answers[0]
        if isinstance(step, Exception):
            raise step
        return step


def serve(monkeypatch, *answers) -> Portal:
    portal = Portal(answers)
    monkeypatch.setattr(groundwater.requests, "request", portal)
    return portal


def by_variable(values, lgd: int) -> dict:
    rows = values[values["districtLgd"] == lgd]
    return {row.variable: (row.stat, row.value, row.unit) for row in rows.itertuples()}


def test_a_name_is_compared_folded_without_spacing_or_punctuation():
    assert groundwater.name_key("  Sawai   Madhopur ") == "sawai madhopur"
    assert groundwater.name_key("Didwana-Kuchaman") == "didwana kuchaman"
    assert groundwater.name_key("SRI GANGANAGAR") == "sri ganganagar"
    assert groundwater.name_key("Total") == "total"


def test_each_spelling_is_one_rajasthan_district_the_register_spells_otherwise():
    register = load_register()
    names = {name for state, name in register.districts.values() if state == RAJASTHAN}
    folded = {groundwater.name_key(name) for name in names}
    assert set(groundwater.SPELLINGS.values()) <= names
    assert [spelling for spelling in groundwater.SPELLINGS if spelling in folded] == []
    assert all(groundwater.name_key(spelling) == spelling for spelling in groundwater.SPELLINGS)


def test_the_dataset_row_is_the_portal_table_under_its_open_licence():
    assert GROUNDWATER.url == API
    assert (GROUNDWATER.licence, GROUNDWATER.licenceUrl) == (
        "Government Open Data License - India",
        "https://www.data.gov.in/Godl",
    )
    assert GROUNDWATER.redistributable is True
    assert GROUNDWATER.period == groundwater.PERIOD == "2023"


def test_the_table_is_read_page_by_page_with_the_key_into_district_rows(monkeypatch, tmp_path, sleeps):
    monkeypatch.setenv(groundwater.KEY_VARIABLE, KEY)
    monkeypatch.setattr(groundwater, "PAGE_ROWS", 2)
    portal = serve(
        monkeypatch,
        page([AJMER_ROW, CHITTAURGARH_ROW], total=4, offset=0),
        page([JHUNJHUNUN_ROW, TOTAL_ROW], total=4, offset=2),
    )
    result = groundwater.run(load_districts({AJMER, CHITTORGARH, JHUNJHUNU, KACHCHH}), Options(cache=tmp_path))
    assert result.failures == []
    assert [(c["url"], c["offset"], c["limit"], c["api-key"], c["format"]) for c in portal.calls] == [
        (API, 0, 2, KEY, "json"),
        (API, 2, 2, KEY, "json"),
    ]
    assert {c["agent"] for c in portal.calls} == {"kalavigyan-geo-etl/0.0.1"}
    assert sleeps == [1.0]
    values = result.values
    assert list(values.columns) == COLUMNS and len(values) == 21
    assert sorted(set(values["districtLgd"])) == [AJMER, CHITTORGARH, JHUNJHUNU]
    assert by_variable(values, AJMER) == AJMER_VALUES
    assert by_variable(values, JHUNJHUNU)["stage_of_groundwater_extraction"] == ("SHARE", 216.66, "%")
    assert set(values["depthOrPeriod"]) == {"2023"} and set(values["datasetCode"]) == {GROUNDWATER.code}
    methods = dict(zip(values["districtLgd"], values["method"], strict=True))
    assert methods[AJMER] == groundwater.METHOD
    assert methods[CHITTORGARH] == f"{groundwater.METHOD}; the table spells it Chittaurgarh"
    assert result.notes == {
        "states": [RAJASTHAN],
        "districtsOutsideTable": 1,
        "rowsRead": 4,
        "stateTotalRows": 1,
        "spelledAs": {"95": "Chittaurgarh", "106": "Jhunjhunun"},
    }


def test_every_selected_district_is_accounted_for_and_the_table_covers_only_its_state(monkeypatch, tmp_path, sleeps):
    monkeypatch.setenv(groundwater.KEY_VARIABLE, KEY)
    serve(monkeypatch, page([AJMER_ROW, TOTAL_ROW], total=2, offset=0))
    districts = load_districts({AJMER, JHUNJHUNU, KACHCHH})
    result = groundwater.run(districts, Options(cache=tmp_path))
    reach = coverage_of(districts, result)
    assert result.states == frozenset({RAJASTHAN})
    assert [item["districtLgds"] for item in result.failures] == [[JHUNJHUNU]]
    assert (reach.districts_without_values, reach.silent_districts, reach.lost_states) == ([JHUNJHUNU], [], [])


def test_rows_naming_no_district_or_one_twice_and_districts_without_a_row_are_failures(monkeypatch, tmp_path, sleeps):
    monkeypatch.setenv(groundwater.KEY_VARIABLE, KEY)
    city = AJMER_ROW | {"sl__no_": "3", "name_of_district": "Ajmer City"}
    serve(monkeypatch, page([AJMER_ROW, AJMER_ROW | {"sl__no_": "2"}, city], total=3, offset=0))
    result = groundwater.run(load_districts({AJMER, JHUNJHUNU}), Options(cache=tmp_path))
    assert result.values.empty
    assert result.failures == [
        {
            "step": "groundwater match",
            "districtLgds": [],
            "error": "row 3 names 'Ajmer City', which matches 0 districts of state 8",
        },
        {"step": "groundwater match", "districtLgds": [AJMER], "error": "district 86 is named by rows [1, 2]"},
        {"step": "groundwater match", "districtLgds": [JHUNJHUNU], "error": "the table has no row for Jhunjhunu (106)"},
    ]


def test_a_figure_that_is_not_a_number_fails_only_its_own_field(monkeypatch, tmp_path, sleeps):
    monkeypatch.setenv(groundwater.KEY_VARIABLE, KEY)
    broken = AJMER_ROW | {"current_annual_ground_water_extraction___industrial": "NA"}
    serve(monkeypatch, page([broken], total=1, offset=0))
    result = groundwater.run(load_districts({AJMER}), Options(cache=tmp_path))
    assert result.failures == [
        {
            "step": "groundwater match",
            "districtLgds": [AJMER],
            "error": "current_annual_ground_water_extraction___industrial of Ajmer reads 'NA', not a number",
        }
    ]
    expected = {k: v for k, v in AJMER_VALUES.items() if k != "annual_groundwater_extraction_industrial"}
    assert by_variable(result.values, AJMER) == expected


def test_without_the_key_the_read_fails_naming_the_variable_and_asks_nothing(monkeypatch, tmp_path, sleeps):
    monkeypatch.delenv(groundwater.KEY_VARIABLE, raising=False)
    portal = serve(monkeypatch, page([AJMER_ROW], total=1, offset=0))
    result = groundwater.run(load_districts({AJMER, JHUNJHUNU}), Options(cache=tmp_path))
    assert portal.calls == [] and result.values.empty
    (item,) = result.failures
    assert (item["step"], item["districtLgds"]) == ("groundwater read", [AJMER, JHUNJHUNU])
    assert item["error"].startswith("MissingKey: DATA_GOV_IN_API_KEY is not set")


def test_a_refused_key_is_not_retried_and_no_failure_carries_the_key(monkeypatch, tmp_path, sleeps):
    monkeypatch.setenv(groundwater.KEY_VARIABLE, KEY)
    portal = serve(monkeypatch, answer(403, {"error": f"key {KEY} is not authorised"}))
    result = groundwater.run(load_districts({AJMER}), Options(cache=tmp_path))
    assert len(portal.calls) == 1 and sleeps == []
    assert [item["error"] for item in result.failures] == ["PortalError: data.gov.in refused rows from 0: 403"]
    assert KEY not in json.dumps(result.failures) + json.dumps(result.notes)


def test_an_unanswered_read_is_retried_then_fails_without_the_address(monkeypatch, tmp_path, sleeps):
    monkeypatch.setenv(groundwater.KEY_VARIABLE, KEY)
    lost = requests.ConnectionError(f"Max retries exceeded with url: /resource/x?api-key={KEY}")
    portal = serve(monkeypatch, lost)
    result = groundwater.run(load_districts({AJMER}), Options(cache=tmp_path))
    assert len(portal.calls) == 4 and sleeps == [5.0, 10.0, 15.0]
    assert [item["error"] for item in result.failures] == [
        "PortalBusy: data.gov.in did not answer for rows from 0: ConnectionError"
    ]
    assert KEY not in json.dumps(result.failures)


def test_a_busy_portal_is_asked_again(monkeypatch, tmp_path, sleeps):
    monkeypatch.setenv(groundwater.KEY_VARIABLE, KEY)
    portal = serve(monkeypatch, answer(503, {}), page([AJMER_ROW], total=1, offset=0))
    result = groundwater.run(load_districts({AJMER}), Options(cache=tmp_path))
    assert len(portal.calls) == 2 and sleeps == [5.0]
    assert result.failures == [] and by_variable(result.values, AJMER) == AJMER_VALUES


def test_a_table_that_lost_a_field_or_rows_fails_the_read(monkeypatch, tmp_path, sleeps):
    monkeypatch.setenv(groundwater.KEY_VARIABLE, KEY)
    serve(monkeypatch, page([AJMER_ROW], total=1, offset=0, fields=FIELD_LIST[:-1]))
    result = groundwater.run(load_districts({AJMER}), Options(cache=tmp_path))
    assert [item["error"] for item in result.failures] == [
        "PortalError: the groundwater table no longer has the fields ['stage_of_ground_water_extraction____']"
    ]
    portal = serve(monkeypatch, page([AJMER_ROW], total=3, offset=0), page([], total=3, offset=1))
    result = groundwater.run(load_districts({AJMER}), Options(cache=tmp_path))
    assert [c["offset"] for c in portal.calls] == [0, 1]
    assert [item["error"] for item in result.failures] == [
        "PortalError: data.gov.in states 3 rows of the groundwater table but sent 1"
    ]


def test_a_selection_outside_the_table_s_state_reads_nothing_and_needs_no_key(monkeypatch, tmp_path, sleeps):
    monkeypatch.delenv(groundwater.KEY_VARIABLE, raising=False)
    portal = serve(monkeypatch, page([AJMER_ROW], total=1, offset=0))
    result = groundwater.run(load_districts({KACHCHH}), Options(cache=tmp_path))
    assert portal.calls == [] and result.failures == []
    assert list(result.values.columns) == COLUMNS and result.values.empty
    assert result.notes == {"states": [RAJASTHAN], "districtsOutsideTable": 1}


@pytest.mark.parametrize("figure", [None, "", " ", True, float("nan"), {"value": 1}])
def test_a_figure_states_a_number_or_nothing_usable(figure):
    with pytest.raises((TypeError, ValueError)):
        groundwater.stated_number(figure)
