import datetime as dt
import hashlib
import json
import zipfile
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from river_fixture import PLACEHOLDER_OUTLET, PLACEHOLDER_REACHES, placeholder_basin
from shapely.geometry import LineString, MultiLineString, Polygon, box

from geo_etl import rivers, topology
from geo_etl.__main__ import main
from geo_etl.districts import load_districts
from geo_etl.river_districts import REACH_DISTRICTS_FILE, districts_by_reach, reach_districts
from geo_etl.rivers import (
    BASINS_FILE,
    REACHES_FILE,
    RiverNetworkError,
    basins_crossing,
    cycle_members,
    india_reaches,
    network_problems,
    single_lines,
    topology_file_name,
    topology_key,
    write_rivers,
)

SHARED = Path(__file__).resolve().parents[3] / "shared"
SOURCE, BEND, TRIBUTARY, MOUTH = 41000010, 41000020, 41000030, 41000040
COAST = 41000090
KACHCHH = 449


def reach(hyriv_id, next_down, main_riv, coords, *, upland=150.0, order=2):
    return {
        "hyrivId": hyriv_id,
        "nextDown": next_down,
        "mainRiv": main_riv,
        "ordStra": order,
        "uplandSkm": upland,
        "disAvCms": 0.5,
        "lengthKm": 4.2,
        "geometry": LineString(coords),
    }


def network(*rows) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(list(rows), geometry="geometry", crs="EPSG:4326")


def kachchh_like() -> gpd.GeoDataFrame:
    return network(
        reach(SOURCE, BEND, MOUTH, [(69.00, 23.60), (69.03, 23.55), (69.10, 23.50)], upland=120.0),
        reach(TRIBUTARY, BEND, MOUTH, [(69.20, 23.70), (69.10, 23.50)], upland=110.0),
        reach(BEND, MOUTH, MOUTH, [(69.10, 23.50), (69.1004, 23.4501), (69.10, 23.40)], upland=400.0, order=3),
        reach(MOUTH, 0, MOUTH, [(69.10, 23.40), (69.20, 23.10)], upland=520.0, order=3),
        reach(COAST, 0, COAST, [(75.00, 15.00), (75.10, 14.90)], upland=130.0),
    )


def districts() -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        {"districtLgd": [449], "stateLgd": [24]}, geometry=[box(69.05, 23.30, 69.30, 23.45)], crs="EPSG:4326"
    )


@pytest.mark.parametrize(
    "row", json.loads((SHARED / "naming-golden.json").read_text(encoding="utf-8"))["riverTopologies"]
)
def test_the_topology_key_is_the_naming_golden_row(row):
    assert topology_file_name(row["mainRiv"]) == row["fileName"]
    assert topology_key(row["edition"], row["mainRiv"], row["sha256"]) == row["key"]


def test_a_topology_key_refuses_an_edition_id_or_digest_it_cannot_file():
    digest = hashlib.sha256(b"").hexdigest()
    with pytest.raises(ValueError, match="ASCII edition"):
        topology_key("v10/../x", MOUTH, digest)
    with pytest.raises(ValueError, match="outlet reach id"):
        topology_key("v10", 0, digest)
    with pytest.raises(ValueError, match="SHA-256"):
        topology_key("v10", MOUTH, digest.upper())


def test_a_kept_network_has_no_problems():
    assert network_problems(kachchh_like()) == []


def test_every_broken_rule_is_named_with_its_reach():
    broken = network(
        reach(SOURCE, SOURCE, MOUTH, [(0, 0), (1, 1)]),
        reach(BEND, 0, MOUTH, [(0, 0), (1, 1)]),
        reach(TRIBUTARY, 41999999, MOUTH, [(0, 0), (1, 1)]),
        reach(MOUTH, 0, MOUTH, [(0, 0), (1, 1)]),
        reach(COAST, 0, COAST, [(0, 0), (1, 1)], order=16),
        reach(41000050, MOUTH, COAST, [(0, 0), (1, 1)]),
        reach(41000050, MOUTH, COAST, [(0, 0), (1, 1)]),
    )
    assert network_problems(broken) == [
        "reach 41000050 is listed twice",
        f"reach {SOURCE} flows into itself",
        f"reach {BEND} ends its river exactly when it is the river's outlet",
        f"reach {TRIBUTARY} flows into 41999999, which is not kept",
        f"reach 41000050 of river {COAST} flows into {MOUTH} of river {MOUTH}",
        f"reach {COAST} has ordStra 16",
        f"reach {SOURCE} flows in a cycle",
    ]


def test_a_cycle_is_found_wherever_the_walk_starts():
    assert cycle_members({1: 2, 2: 3, 3: 2, 4: 3, 5: 0}) == [2, 3]
    assert cycle_members({1: 0, 2: 1}) == []


def test_a_multi_part_line_is_merged_or_named():
    joined = MultiLineString([[(0, 0), (1, 1)], [(1, 1), (2, 1)]])
    apart = MultiLineString([[(0, 0), (1, 1)], [(5, 5), (6, 6)]])
    frame = single_lines(network(reach(MOUTH, 0, MOUTH, [(0, 0), (1, 1)])).set_geometry([joined]))
    assert frame.geometry.iloc[0].equals(LineString([(0, 0), (1, 1), (2, 1)]))
    split = single_lines(network(reach(MOUTH, 0, MOUTH, [(0, 0), (1, 1)])).set_geometry([apart]))
    assert network_problems(split) == [f"reach {MOUTH} is not one line"]


def test_a_basin_is_kept_whole_when_one_of_its_reaches_crosses_a_district():
    reaches = kachchh_like()
    assert basins_crossing(reaches, districts()) == {MOUTH}
    kept = india_reaches(reaches, districts())
    assert kept["hyrivId"].tolist() == [SOURCE, BEND, TRIBUTARY, MOUTH]


def decoded(topo: dict) -> dict[int, list[tuple[int, int]]]:
    positions = {}
    for geometry in topo["objects"][topology.OBJECT]["geometries"]:
        x = y = 0
        points = []
        for dx, dy in topo["arcs"][geometry["arcs"][0]]:
            x, y = x + dx, y + dy
            points.append((x, y))
        positions[geometry["id"]] = points
    return positions


def test_the_simplified_topology_keeps_every_junction():
    reaches = kachchh_like()
    basin = reaches[reaches["mainRiv"] == MOUTH]
    topo = topology.basin_topology(basin, {})
    lines = decoded(topo)
    for _, row in basin.iterrows():
        if row["nextDown"]:
            assert lines[row["hyrivId"]][-1] == lines[row["nextDown"]][0]
    assert len(lines[BEND]) == 2
    assert len(lines[SOURCE]) == 3


def test_the_topology_is_quantized_over_the_basin_and_carries_its_reaches():
    reaches = kachchh_like()
    hits = districts_by_reach(reach_districts(reaches, districts()))
    topo = topology.basin_topology(reaches[reaches["mainRiv"] == MOUTH], hits)
    assert topo["bbox"] == [69.0, 23.1, 69.2, 23.7]
    scale, translate = topo["transform"]["scale"], topo["transform"]["translate"]
    assert translate == [69.0, 23.1]
    assert scale == pytest.approx([0.2 / 99_999, 0.6 / 99_999])
    lines = decoded(topo)
    assert lines[TRIBUTARY][0] == (99_999, 99_999)
    assert lines[MOUTH][-1] == (99_999, 0)
    assert lines[SOURCE][0][0] == 0
    geometries = topo["objects"][topology.OBJECT]["geometries"]
    assert [(g["id"], g["properties"]) for g in geometries] == [
        (SOURCE, {"nextDown": BEND, "ordStra": 2, "districts": []}),
        (BEND, {"nextDown": MOUTH, "ordStra": 3, "districts": [[449, 0.5]]}),
        (TRIBUTARY, {"nextDown": BEND, "ordStra": 2, "districts": []}),
        (MOUTH, {"nextDown": 0, "ordStra": 3, "districts": [[449, 0.0]]}),
    ]


def test_a_reach_shorter_than_one_step_keeps_two_positions():
    topo = topology.basin_topology(
        network(
            reach(MOUTH, 0, MOUTH, [(70.0, 20.0), (70.0000001, 20.0000001)]),
            reach(COAST, MOUTH, MOUTH, [(71.0, 21.0), (70.0, 20.0)]),
        ),
        {},
    )
    assert decoded(topo)[MOUTH] == [(0, 0), (0, 0)]


def test_write_rivers_writes_reaches_topologies_and_their_hashes(tmp_path):
    reaches = india_reaches(kachchh_like(), districts())
    hits = reach_districts(reaches, districts())
    manifest = write_rivers(reaches, hits, tmp_path, retrieved_at=dt.datetime(2026, 11, 17, tzinfo=dt.UTC))
    assert (tmp_path / REACHES_FILE).is_file()
    assert json.loads((tmp_path / BASINS_FILE).read_text(encoding="utf-8")) == manifest
    assert manifest["uplandMinSkm"] == 100
    assert manifest["reaches"] == 4
    assert manifest["reachDistricts"] == 2
    assert pd.read_parquet(tmp_path / REACH_DISTRICTS_FILE).values.tolist() == [[BEND, 449, 0.5], [MOUTH, 449, 0.0]]
    assert manifest["dataset"]["code"] == "HYDRORIVERS_1_0"
    [basin] = manifest["basins"]
    body = (tmp_path / basin["file"]).read_bytes()
    assert (basin["mainRiv"], basin["reaches"], basin["bytes"]) == (MOUTH, 4, len(body))
    assert basin["sha256"] == hashlib.sha256(body).hexdigest()
    assert gpd.read_parquet(tmp_path / REACHES_FILE)["hyrivId"].tolist() == [SOURCE, BEND, TRIBUTARY, MOUTH]


def test_build_writes_nothing_for_a_broken_network(monkeypatch, tmp_path):
    broken = network(reach(MOUTH, BEND, MOUTH, [(69.10, 23.40), (69.20, 23.10)]))
    monkeypatch.setattr(rivers, "cached_archive", lambda cache: cache / "archive.zip")
    monkeypatch.setattr(rivers, "read_reaches", lambda archive: broken)
    monkeypatch.setattr(rivers, "load_districts", districts)
    with pytest.raises(RiverNetworkError) as raised:
        rivers.build(tmp_path / "out", cache=tmp_path)
    assert raised.value.problems == [f"reach {MOUTH} ends its river exactly when it is the river's outlet"]
    assert not (tmp_path / "out").exists()


def test_the_rivers_command_reports_what_it_wrote_or_why_it_wrote_nothing(monkeypatch, tmp_path, capsys):
    manifest = {"reaches": 4, "basins": [{"bytes": 900}, {"bytes": 1200}]}
    monkeypatch.setattr(rivers, "build", lambda out, cache: manifest)
    assert main(["rivers", "--out", str(tmp_path), "--cache", str(tmp_path)]) == 0
    assert "4 reaches in 2 basins" in capsys.readouterr().out

    def broken(out, cache):
        raise RiverNetworkError([f"reach {MOUTH} flows in a cycle"])

    monkeypatch.setattr(rivers, "build", broken)
    assert main(["rivers", "--out", str(tmp_path), "--cache", str(tmp_path)]) == 1
    assert f"reach {MOUTH} flows in a cycle" in capsys.readouterr().err


def test_the_placeholder_basin_reproduces_the_shared_river_golden():
    golden = (SHARED / "river.topology.golden.json").read_bytes()
    basin = placeholder_basin()
    topo = topology.basin_topology(basin, districts_by_reach(reach_districts(basin, load_districts({KACHCHH}))))
    assert topology.encoded(topo) + b"\n" == golden
    lines = decoded(topo)
    for hyriv_id, next_down, *_ in PLACEHOLDER_REACHES:
        if next_down:
            assert lines[hyriv_id][-1] == lines[next_down][0]
    assert lines[1][0] == (0, 89_285)
    assert lines[PLACEHOLDER_OUTLET][-1] == (99_999, 0)


def test_read_reaches_keeps_only_reaches_of_the_threshold_from_the_zipped_shapefile(tmp_path):
    source = network(
        reach(SOURCE, BEND, MOUTH, [(69.0, 23.6), (69.1, 23.5)], upland=99.9),
        reach(BEND, MOUTH, MOUTH, [(69.1, 23.5), (69.1, 23.4)], upland=100.0),
        reach(MOUTH, 0, MOUTH, [(69.1, 23.4), (69.2, 23.1)], upland=520.0),
    ).rename(columns={v: k for k, v in rivers.SOURCE_FIELDS.items()})
    source["ORD_FLOW"] = 6
    folder = tmp_path / "HydroRIVERS_v10_as_shp"
    folder.mkdir()
    source.to_file(folder / "HydroRIVERS_v10_as.shp", driver="ESRI Shapefile")
    archive = tmp_path / "HydroRIVERS_v10_as_shp.zip"
    with zipfile.ZipFile(archive, "w") as handle:
        for part in sorted(folder.iterdir()):
            handle.write(part, f"{folder.name}/{part.name}")
    reaches = rivers.read_reaches(archive)
    assert list(reaches.columns) == rivers.REACH_COLUMNS
    assert reaches["hyrivId"].tolist() == [BEND, MOUTH]
    assert reaches.crs.to_epsg() == 4326
    assert network_problems(reaches) == []


def test_a_reach_enters_each_district_it_crosses_at_its_first_point_inside():
    line = network(
        reach(MOUTH, 0, MOUTH, [(0.0, 0.0), (10.0, 0.0)]),
        reach(COAST, 0, COAST, [(0.0, 5.0), (1.0, 5.0)]),
    )
    corner = Polygon([(6.0, 0.0), (5.0, -1.0), (7.0, -1.0)])
    shapes = gpd.GeoDataFrame(
        {"districtLgd": [101, 102, 103]},
        geometry=[box(-1.0, -1.0, 4.0, 1.0), box(4.0, -1.0, 11.0, 1.0), corner],
        crs="EPSG:4326",
    )
    hits = reach_districts(line, shapes)
    assert hits.values.tolist() == [[MOUTH, 101, 0.0], [MOUTH, 102, 0.4], [MOUTH, 103, 0.6]]
    assert districts_by_reach(hits) == {MOUTH: [[101, 0.0], [102, 0.4], [103, 0.6]]}


def test_reaches_in_no_district_have_no_hits():
    far = network(reach(COAST, 0, COAST, [(75.00, 15.00), (75.10, 14.90)]))
    hits = reach_districts(far, districts())
    assert list(hits.columns) == ["hyrivId", "districtLgd", "entry"]
    assert hits.empty
