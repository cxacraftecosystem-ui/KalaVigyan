import math
import os
import re
import time
import unicodedata
from dataclasses import dataclass, field
from functools import partial

import geopandas as gpd
import pandas as pd
import requests

from geo_etl.catalog import GROUNDWATER
from geo_etl.districts import load_register
from geo_etl.layers import USER_AGENT, Options, Result, failure, with_retries
from geo_etl.rows import Rows

__all__ = [
    "DISTRICT_FIELD",
    "FIELDS",
    "KEY_VARIABLE",
    "METHOD",
    "PAGE_PAUSE_S",
    "PAGE_ROWS",
    "PERIOD",
    "SPELLINGS",
    "STATES",
    "STATE_LGD",
    "Matching",
    "MissingKey",
    "PortalBusy",
    "PortalError",
    "Table",
    "match_rows",
    "name_key",
    "read_table",
    "register_keys",
    "run",
]

KEY_VARIABLE = "DATA_GOV_IN_API_KEY"
STATE_LGD = 8
STATES = frozenset({STATE_LGD})
PERIOD = "2023"
PAGE_ROWS = 100
PAGE_PAUSE_S = 1.0
TIMEOUT_S = (10, 60)
RETRIED_STATUSES = (429, 500, 502, 503, 504)
HEADERS = {"User-Agent": USER_AGENT, "Accept": "application/json"}
DISTRICT_FIELD = "name_of_district"
STATE_TOTAL = "total"
MATCH_STEP = "groundwater match"
READ_STEP = "groundwater read"
FIELDS: dict[str, tuple[str, str, str]] = {
    "total_annual_ground_water_recharge": ("annual_groundwater_recharge", "TOTAL", "ham"),
    "annual_extractable_ground_water_resource": ("annual_extractable_groundwater", "TOTAL", "ham"),
    "current_annual_ground_water_extraction___irrigation": (
        "annual_groundwater_extraction_irrigation",
        "TOTAL",
        "ham",
    ),
    "current_annual_ground_water_extraction___industrial": (
        "annual_groundwater_extraction_industrial",
        "TOTAL",
        "ham",
    ),
    "current_annual_ground_water_extraction___domestic": ("annual_groundwater_extraction_domestic", "TOTAL", "ham"),
    "current_annual_ground_water_extraction___total": ("annual_groundwater_extraction", "TOTAL", "ham"),
    "stage_of_ground_water_extraction____": ("stage_of_groundwater_extraction", "SHARE", "%"),
}
SPELLINGS: dict[str, str] = {
    "chittaurgarh": "Chittorgarh",
    "dhaulpur": "Dholpur",
    "jalor": "Jalore",
    "jhunjhunun": "Jhunjhunu",
    "sri ganganagar": "Ganganagar",
}
METHOD = "the district's figure as the table states it, for the district as listed before Rajasthan's reorganisation"


class PortalError(RuntimeError):
    pass


class PortalBusy(PortalError):
    pass


class MissingKey(PortalError):
    pass


@dataclass(frozen=True)
class Table:
    fields: tuple[str, ...]
    records: tuple[dict, ...]


@dataclass
class Matching:
    rows: dict[int, dict] = field(default_factory=dict)
    spelled: dict[int, str] = field(default_factory=dict)
    failures: list[dict] = field(default_factory=list)
    state_totals: int = 0


def name_key(text: str) -> str:
    folded = unicodedata.normalize("NFKC", text).casefold()
    return " ".join(re.sub(r"[\W_]+", " ", folded).split())


def run(districts: gpd.GeoDataFrame, options: Options) -> Result:
    scoped = districts[districts["stateLgd"].isin(sorted(STATES))]
    rows = Rows(GROUNDWATER, METHOD)
    notes: dict = {"states": sorted(STATES), "districtsOutsideTable": int(len(districts) - len(scoped))}
    if scoped.empty:
        return Result(GROUNDWATER, rows.frame(), notes=notes, states=STATES)
    try:
        table = read_table(api_key())
        check_fields(table)
    except Exception as error:
        failures = [failure(scoped, READ_STEP, error)]
        return Result(GROUNDWATER, rows.frame(), failures=failures, notes=notes, states=STATES)
    matching = match_rows(table.records, register_keys())
    failures = [*matching.failures, *write_values(rows, scoped, matching)]
    notes |= {
        "rowsRead": len(table.records),
        "stateTotalRows": matching.state_totals,
        "spelledAs": {str(lgd): text for lgd, text in sorted(matching.spelled.items())},
    }
    return Result(GROUNDWATER, rows.frame(), failures=failures, notes=notes, states=STATES)


def api_key() -> str:
    key = os.environ.get(KEY_VARIABLE, "").strip()
    if not key:
        raise MissingKey(f"{KEY_VARIABLE} is not set: the groundwater table is read from data.gov.in with that key")
    return key


def read_table(key: str) -> Table:
    records: list[dict] = []
    fields: tuple[str, ...] = ()
    total: int | None = None
    while total is None or len(records) < total:
        if records:
            time.sleep(PAGE_PAUSE_S)
        body = with_retries(partial(fetch_page, key, len(records)), retry_on=(PortalBusy,))
        fields = fields or tuple(str(item.get("id")) for item in body.get("field") or [])
        total = stated_total(body)
        page = body.get("records") or []
        if not page:
            break
        records.extend(page)
    if len(records) != total:
        raise PortalError(f"data.gov.in states {total} rows of the groundwater table but sent {len(records)}")
    return Table(fields, tuple(records))


def fetch_page(key: str, offset: int) -> dict:
    params = {"api-key": key, "format": "json", "limit": PAGE_ROWS, "offset": offset}
    try:
        response = requests.request("GET", GROUNDWATER.url, params=params, headers=HEADERS, timeout=TIMEOUT_S)
    except requests.RequestException as error:
        raise PortalBusy(f"data.gov.in did not answer for rows from {offset}: {type(error).__name__}") from None
    if response.status_code in RETRIED_STATUSES:
        raise PortalBusy(f"data.gov.in answered {response.status_code} for rows from {offset}")
    if response.status_code != 200:
        raise PortalError(f"data.gov.in refused rows from {offset}: {response.status_code}")
    try:
        body = response.json()
    except ValueError:
        raise PortalError(f"data.gov.in sent rows from {offset} that are not JSON") from None
    if not isinstance(body, dict) or body.get("status") != "ok":
        raise PortalError(f"data.gov.in did not answer ok for rows from {offset}")
    return body


def stated_total(body: dict) -> int:
    try:
        return int(body["total"])
    except KeyError, TypeError, ValueError:
        raise PortalError("data.gov.in did not state how many rows the groundwater table has") from None


def check_fields(table: Table) -> None:
    missing = [name for name in (DISTRICT_FIELD, *FIELDS) if name not in table.fields]
    if missing:
        raise PortalError(f"the groundwater table no longer has the fields {missing}")


def register_keys(state_lgd: int = STATE_LGD) -> dict[str, list[int]]:
    keys: dict[str, list[int]] = {}
    for lgd, (state, name) in sorted(load_register().districts.items()):
        if state == state_lgd:
            keys.setdefault(name_key(name), []).append(lgd)
    return keys


def match_rows(records: tuple[dict, ...], keys: dict[str, list[int]]) -> Matching:
    matching = Matching()
    claimed: dict[int, list[int]] = {}
    for number, record in enumerate(records, start=1):
        text = str(record.get(DISTRICT_FIELD) or "").strip()
        key = name_key(text)
        if key == STATE_TOTAL:
            matching.state_totals += 1
            continue
        lgds = keys.get(name_key(SPELLINGS[key]) if key in SPELLINGS else key, [])
        if len(lgds) != 1:
            error = f"row {number} names {text!r}, which matches {len(lgds)} districts of state {STATE_LGD}"
            matching.failures.append(row_failure(lgds, error))
            continue
        claimed.setdefault(lgds[0], []).append(number)
        matching.rows[lgds[0]] = record
        if key in SPELLINGS:
            matching.spelled[lgds[0]] = text
    drop_claimed_twice(matching, claimed)
    return matching


def drop_claimed_twice(matching: Matching, claimed: dict[int, list[int]]) -> None:
    for lgd, numbers in sorted(claimed.items()):
        if len(numbers) > 1:
            matching.rows.pop(lgd)
            matching.spelled.pop(lgd, None)
            matching.failures.append(row_failure([lgd], f"district {lgd} is named by rows {numbers}"))


def write_values(rows: Rows, scoped: gpd.GeoDataFrame, matching: Matching) -> list[dict]:
    failures: list[dict] = []
    named = {lgd for item in matching.failures for lgd in item["districtLgds"]}
    for _, district in scoped.iterrows():
        lgd = int(district["districtLgd"])
        record = matching.rows.get(lgd)
        if record is not None:
            failures += add_district(rows, district, record, spelled=matching.spelled.get(lgd))
        elif lgd not in named:
            failures.append(row_failure([lgd], f"the table has no row for {district['districtName']} ({lgd})"))
    return failures


def add_district(rows: Rows, district: pd.Series, record: dict, *, spelled: str | None) -> list[dict]:
    method = METHOD if spelled is None else f"{METHOD}; the table spells it {spelled}"
    failures: list[dict] = []
    for name, (variable, stat, unit) in FIELDS.items():
        try:
            value = stated_number(record.get(name))
        except TypeError, ValueError:
            error = f"{name} of {district['districtName']} reads {record.get(name)!r}, not a number"
            failures.append(row_failure([int(district["districtLgd"])], error))
            continue
        rows.add(district, variable, PERIOD, stat, value, unit, method=method)
    return failures


def stated_number(value: object) -> float:
    if value is None or isinstance(value, bool) or (isinstance(value, str) and not value.strip()):
        raise ValueError(f"{value!r} states no figure")
    if not isinstance(value, int | float | str):
        raise TypeError(f"{value!r} is not a figure")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{value!r} is not finite")
    return number


def row_failure(lgds: list[int], error: str) -> dict:
    return {"step": MATCH_STEP, "districtLgds": sorted(lgds), "error": error[:500]}
