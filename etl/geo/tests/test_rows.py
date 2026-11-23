import math

import pandas as pd
import pytest

from geo_etl.catalog import SOILGRIDS
from geo_etl.rows import COLUMNS, STATS, Rows, pick

MAHE = pd.Series({"districtLgd": 599, "stateLgd": 34, "districtName": "Mahe"})


def test_add_rejects_unknown_stat():
    rows = Rows(SOILGRIDS, "zonal mean")
    with pytest.raises(ValueError, match="unknown stat"):
        rows.add(MAHE, "clay", "0-5cm", "MEDIAN", 1.0, unit="g/kg")
    assert rows.items == []


@pytest.mark.parametrize("stat", STATS)
def test_add_accepts_every_known_stat(stat):
    rows = Rows(SOILGRIDS, "zonal mean")
    rows.add(MAHE, "clay", "0-5cm", stat, 1.0, unit="g/kg")
    assert rows.items[0]["stat"] == stat


@pytest.mark.parametrize("bad", [math.nan, math.inf, -math.inf, None])
def test_add_drops_non_finite_without_text(bad):
    rows = Rows(SOILGRIDS, "zonal mean")
    rows.add(MAHE, "clay", "0-5cm", "DISTRICT_MEAN", bad, unit="g/kg")
    assert rows.items == []


def test_add_keeps_text_when_value_is_nan():
    rows = Rows(SOILGRIDS, "zonal mean")
    rows.add(MAHE, "landform", "", "CLASS", math.nan, unit="", text="coastal plain")
    assert rows.items[0]["value"] is None
    assert rows.items[0]["valueText"] == "coastal plain"


def test_add_fills_provenance_and_overrides():
    rows = Rows(SOILGRIDS, "zonal mean")
    rows.add(MAHE, "clay", "0-5cm", "DISTRICT_MEAN", 312, unit="g/kg", pixels=96.4)
    rows.add(MAHE, "sand", "0-5cm", "DISTRICT_P10", 1.5, unit="g/kg", method="other", resolution="1 km")
    first, second = rows.items
    assert first["districtLgd"] == 599 and first["stateLgd"] == 34 and first["districtName"] == "Mahe"
    assert first["value"] == 312.0 and isinstance(first["value"], float)
    assert first["pixelCount"] == 96.4
    assert first["datasetCode"] == SOILGRIDS.code
    assert first["source"] == SOILGRIDS.title
    assert first["version"] == SOILGRIDS.edition
    assert first["resolution"] == SOILGRIDS.nativeResolution
    assert first["licence"] == SOILGRIDS.licence
    assert first["method"] == "zonal mean"
    assert second["method"] == "other"
    assert second["resolution"] == "1 km"
    assert second["pixelCount"] is None


def test_frame_has_fixed_columns_even_when_empty():
    rows = Rows(SOILGRIDS, "zonal mean")
    assert list(rows.frame().columns) == COLUMNS
    rows.add(MAHE, "clay", "0-5cm", "DISTRICT_MEAN", 1.0, unit="g/kg")
    rows.add(MAHE, "clay", "0-5cm", "DISTRICT_MAX", math.nan, unit="g/kg")
    frame = rows.frame()
    assert list(frame.columns) == COLUMNS
    assert len(frame) == 1


def test_pick_matches_prefix_and_suffix():
    record = pd.Series({"pixels": 3, "mean_clay": 9, "classes_band1": [1, 2]})
    assert pick(record, "classes") == [1, 2]
    assert pick(record, "pixels") == 3
    assert pick({"mean": 4}, "mean") == 4
    with pytest.raises(KeyError):
        pick(record, "shares")
