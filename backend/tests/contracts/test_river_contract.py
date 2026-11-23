import ast
from pathlib import Path
from typing import Any

from app.geo.rainfall import RAINFALL_STAT, RAINFALL_UNIT, RAINFALL_VARIABLE, month_periods
from app.models import RiverBasin, RiverReach, RiverReachDistrict
from app.models.rivers import STRAHLER_MAX
from app.research.rivers import (
    HYDRORIVERS_DATASET_CODE,
    MOUTH,
    RIVER_NAME_DATASET_CODES,
    RIVER_REACHES_OBJECT,
)
from app.services import naming
from app.services.river_topology import TOPOLOGY_TYPE

from .golden import REPO
from .phase_b_golden import catalog_dataset, geo_etl_datasets

GEO_ETL = REPO / "etl" / "geo"
STAMPS = {"createdAt", "updatedAt"}


def constants(path: Path) -> dict[str, Any]:
    found: dict[str, Any] = {}
    for node in ast.parse(path.read_text(encoding="utf-8")).body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            try:
                found[node.targets[0].id] = ast.literal_eval(node.value)
            except ValueError:
                continue
    return found


def test_the_etl_writes_the_reach_columns_the_backend_stores() -> None:
    rivers = constants(GEO_ETL / "geo_etl" / "rivers.py")
    loader = constants(GEO_ETL / "load_rivers.py")
    reach_columns = [c.name for c in RiverReach.__table__.columns if c.name not in STAMPS]
    basin_columns = [c.name for c in RiverBasin.__table__.columns if c.name not in STAMPS]
    assert [*rivers["SOURCE_FIELDS"].values(), "geom"] == reach_columns == loader["REACH_COLUMNS"]
    assert loader["BASIN_COLUMNS"] == basin_columns
    assert (loader["BASIN_TABLE"], loader["REACH_TABLE"]) == (
        RiverBasin.__tablename__,
        RiverReach.__tablename__,
    )


def test_the_etl_writes_the_reach_districts_the_backend_reads() -> None:
    hits = constants(GEO_ETL / "geo_etl" / "river_districts.py")
    loader = constants(GEO_ETL / "load_rivers.py")
    assert hits["HIT_COLUMNS"] == [c.name for c in RiverReachDistrict.__table__.columns]
    assert loader["REACH_DISTRICT_TABLE"] == RiverReachDistrict.__tablename__


def test_the_river_names_datasets_are_the_registry_s_and_the_contract_s() -> None:
    assert set(RIVER_NAME_DATASET_CODES) <= set(geo_etl_datasets())
    assert catalog_dataset("OSM_RIVER_NAMES")["attribution"] == "© OpenStreetMap contributors"
    assert catalog_dataset("OSM_RIVER_NAMES")["licence"] == "ODbL 1.0"
    assert catalog_dataset("WIKIDATA_RIVER_NAMES")["licence"] == "CC0 1.0"


def test_the_etl_keeps_the_contract_s_network_rules_and_files() -> None:
    rivers = constants(GEO_ETL / "geo_etl" / "rivers.py")
    topology = constants(GEO_ETL / "geo_etl" / "topology.py")
    loader = constants(GEO_ETL / "load_rivers.py")
    assert (rivers["STRAHLER_MAX"], rivers["OUTLET"]) == (STRAHLER_MAX, MOUTH)
    assert topology["OBJECT"] == RIVER_REACHES_OBJECT
    assert loader["TOPOLOGY_TYPE"] == TOPOLOGY_TYPE
    assert rivers["TOPOLOGY_PREFIX"] == f"{naming.MEDIA_PREFIX}/{naming.RIVER_FOLDER}"
    assert rivers["TOPOLOGY_SUBJECT"] == naming.RIVER_TOPOLOGY_SUBJECT
    assert catalog_dataset(HYDRORIVERS_DATASET_CODE)["edition"] == "v10"


def monthly_row_call() -> ast.Call:
    tree = ast.parse((GEO_ETL / "geo_etl" / "layers" / "chirps.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "add"
            and len(node.args) >= 6
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value == RAINFALL_VARIABLE
        ):
            return node
    raise AssertionError("the CHIRPS layer writes no monthly normal")


def test_the_chirps_layer_writes_the_monthly_normals_the_seasons_reader_reads() -> None:
    call = monthly_row_call()
    stat, unit = (ast.literal_eval(arg) for arg in (call.args[3], call.args[5]))
    assert (stat, unit) == (RAINFALL_STAT, RAINFALL_UNIT)
    key = call.args[2]
    assert isinstance(key, ast.JoinedStr)
    assert ast.unparse(key) == "f'{period}-{month:02d}'"
    assert month_periods("2016-2025")[6] == "2016-2025-07"
