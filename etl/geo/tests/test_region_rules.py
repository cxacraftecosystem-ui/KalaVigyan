import ast
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pytest
from rasterio.crs import CRS
from rasterio.transform import from_origin
from shapely.geometry import box

from geo_etl import raster
from geo_etl.catalog import GLIM, MRDS
from geo_etl.layers import Options, geology

REPO = Path(__file__).resolve().parents[3]
RULES = json.loads((REPO / "backend" / "app" / "geo" / "region_rules.json").read_text(encoding="utf-8"))
REGION_PROFILE_MIGRATION = REPO / "backend" / "migrations" / "versions" / "0005_region_profile.py"
TWIN = RULES["lithologyTwinPrefix"]
ABSENT = RULES["absentMeansZero"]
SANDS, SANDSTONE = 1.0, 3.0


def two_districts() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"districtLgd": [11, 12], "stateLgd": [1, 1], "districtName": ["rocks", "beyond the grid"]},
        geometry=[box(70.2, 20.2, 71.8, 21.8), box(72.2, 20.2, 73.8, 21.8)],
        crs="EPSG:4326",
    )


def two_rock_types(*args, **kwargs) -> raster.Grid:
    values = np.full((4, 4), np.nan, dtype="float32")
    values[:, 0] = SANDS
    values[:, 1] = SANDSTONE
    return raster.Grid(values, from_origin(70.0, 24.0, 1.0, 1.0), CRS.from_epsg(4326))


@pytest.fixture
def glim(monkeypatch, tmp_path):
    monkeypatch.setattr(raster, "read", two_rock_types)
    monkeypatch.setattr(geology, "download", lambda url, target: target)
    return geology.run_glim(two_districts(), Options(cache=tmp_path))


def site(lon: float, lat: float, dep_id: str, *commodities: str) -> dict:
    return {
        "depId": dep_id,
        "name": f"site {dep_id}",
        "devStat": "Occurrence",
        "commodities": list(commodities),
        "url": "",
        "lon": lon,
        "lat": lat,
    }


@pytest.fixture
def mrds(monkeypatch, tmp_path):
    sites = [site(71.0, 21.0, "1", "AU", "CU"), site(70.5, 20.5, "2", "AU")]
    monkeypatch.setattr(geology, "fetch_mrds", lambda bounds: sites)
    return geology.run_mrds(two_districts(), Options(cache=tmp_path))


def test_the_rules_name_the_datasets_whose_row_builders_this_file_runs():
    assert set(ABSENT) == {GLIM.code, MRDS.code}


def test_glim_writes_each_rock_type_share_as_a_geology_row_and_as_its_twin_value(glim):
    assert glim.failures == []
    shares = {(row["districtLgd"], row["lithology"]): row["areaShare"] for _, row in glim.geology.iterrows()}
    twins = {
        (row["districtLgd"], row["variable"].removeprefix(TWIN)): row["value"] for _, row in glim.values.iterrows()
    }
    assert set(shares) == set(twins) == {(11, "su"), (11, "ss")}
    assert [twins[key] for key in sorted(shares)] == pytest.approx([shares[key] for key in sorted(shares)])
    assert sorted(shares.values()) == pytest.approx([0.5, 0.5])
    assert all(variable.startswith(TWIN) for variable in glim.values["variable"])
    assert set(glim.values["stat"]) == {"SHARE"} and set(glim.values["unit"]) == {"fraction"}


def test_glim_writes_no_row_for_a_rock_type_or_a_district_it_did_not_find(glim):
    assert set(glim.geology["districtLgd"]) == set(glim.values["districtLgd"]) == {11}
    assert glim.districts_without_cells == [12]
    assert all(share > 0 for share in glim.geology["areaShare"])
    assert all(value > 0 for value in glim.values["value"])
    assert "lithology".startswith(ABSENT[GLIM.code])


def test_mrds_writes_a_total_everywhere_and_a_commodity_count_only_where_it_occurs(mrds):
    assert mrds.failures == []
    counts = {(row["districtLgd"], row["variable"]): row["value"] for _, row in mrds.values.iterrows()}
    assert counts == {
        (11, "mineral_occurrences"): 2.0,
        (11, "mineral_occurrences_au"): 2.0,
        (11, "mineral_occurrences_cu"): 1.0,
        (12, "mineral_occurrences"): 0.0,
    }
    prefix = ABSENT[MRDS.code]
    assert all(value > 0 for (_, variable), value in counts.items() if variable.startswith(prefix))
    assert not "mineral_occurrences".startswith(prefix)


def test_mrds_lists_occurrences_as_geology_rows_without_a_share(mrds):
    assert list(mrds.geology["districtLgd"]) == [11, 12]
    assert mrds.geology["areaShare"].isna().all()
    assert [len(json.loads(found)) for found in mrds.geology["mineralOccurrences"]] == [2, 0]


def migration_constant(path: Path, name: str):
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and [getattr(t, "id", None) for t in node.targets] == [name]:
            return ast.literal_eval(node.value)
    raise AssertionError(f"{path.name} defines no {name}")


def test_the_glim_legend_the_region_migration_copied_is_the_one_the_etl_writes():
    legend = migration_constant(REGION_PROFILE_MIGRATION, "GLIM_LEGEND")
    assert dict(legend) == dict(geology.GLIM_CLASSES.values())
    assert migration_constant(REGION_PROFILE_MIGRATION, "GLIM_DATASET") == GLIM.code
