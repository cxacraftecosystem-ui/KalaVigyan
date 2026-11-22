import json

import geopandas as gpd
import pandas as pd
from shapely.geometry import LineString

from geo_etl import river_names_files
from geo_etl.__main__ import main
from geo_etl.osm_rivers import OsmWays, named_ways, read_ways, shown_name
from geo_etl.river_districts import HIT_COLUMNS, REACH_DISTRICTS_FILE
from geo_etl.river_names_files import OSM_FILE, SUMMARY_FILE, WIKIDATA_FILE, build_names
from geo_etl.river_names_osm import OsmName, osm_names, osm_rivers
from geo_etl.river_network import network_of
from geo_etl.rivers import REACHES_FILE

UPPER, LOWER, ELSEWHERE, SPLIT, TAKEN = 701, 705, 702, 704, 703
NORTH = 0.0018
REACHES = [
    (UPPER, LOWER, LOWER, [(70.0, 23.0), (70.1, 23.0)]),
    (LOWER, 0, LOWER, [(70.1, 23.0), (70.2, 23.0)]),
    (ELSEWHERE, 0, ELSEWHERE, [(75.0, 15.0), (75.1, 15.0)]),
    (SPLIT, 0, SPLIT, [(71.0, 23.0), (71.1, 23.0)]),
    (TAKEN, 0, TAKEN, [(72.0, 23.0), (72.1, 23.0)]),
]
WAYS = [
    (1001, "Suran River", [(70.0, 23.0 + NORTH), (70.1, 23.0 + NORTH)]),
    (1002, "Suran River", [(70.1, 23.0 + NORTH), (70.2, 23.0 + NORTH)]),
    (2001, "Ari Nadi", [(71.0, 23.0 + NORTH), (71.05, 23.0 + NORTH)]),
    (2002, "Bari Nadi", [(71.05, 23.0 + NORTH), (71.1, 23.0 + NORTH)]),
    (3001, "Taken River", [(72.0, 23.0 + NORTH), (72.1, 23.0 + NORTH)]),
]


def reaches() -> gpd.GeoDataFrame:
    rows = [
        {
            "hyrivId": rid,
            "nextDown": down,
            "mainRiv": main,
            "ordStra": 2,
            "uplandSkm": 150.0,
            "disAvCms": 1.0,
            "lengthKm": 10.0,
            "geometry": LineString(coords),
        }
        for rid, down, main, coords in REACHES
    ]
    return gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")


def ways() -> gpd.GeoDataFrame:
    rows = [{"osmWay": way, "name": name, "geometry": LineString(coords)} for way, name, coords in WAYS]
    return gpd.GeoDataFrame(rows, geometry="geometry", crs="EPSG:4326")


def test_a_way_is_named_by_its_english_or_latin_name_only():
    assert shown_name({"name": "नर्मदा नदी", "name:en": "Narmada River"}) == "Narmada River"
    assert shown_name({"name": "Suran River"}) == "Suran River"
    assert shown_name({"name": "नर्मदा नदी"}) is None
    assert shown_name({"name:en": "", "name": "Sabarmati (Sabar)"}) == "Sabarmati (Sabar)"


def test_the_export_is_read_as_named_river_ways():
    feature = {
        "type": "Feature",
        "id": "w1001",
        "geometry": {"type": "LineString", "coordinates": [[70.0, 23.0], [70.1, 23.0]]},
        "properties": {"waterway": "river", "name": "Suran River"},
    }
    lines = [
        "\x1e" + json.dumps(feature),
        json.dumps(feature | {"id": "w1002", "properties": {"name": "सुरन"}}),
        json.dumps(feature | {"id": "n5", "geometry": {"type": "Point", "coordinates": [70.0, 23.0]}}),
        "",
    ]
    assert [(row["osmWay"], row["name"]) for row in named_ways(lines)] == [(1001, "Suran River")]


def test_read_ways_builds_a_frame_in_longitude_and_latitude(tmp_path):
    path = tmp_path / "rivers.geojsonseq"
    path.write_text(
        json.dumps(
            {
                "type": "Feature",
                "id": "w7",
                "geometry": {"type": "LineString", "coordinates": [[70.0, 23.0], [70.1, 23.0]]},
                "properties": {"name": "Rukmavati River"},
            }
        )
        + "\n",
        encoding="utf-8",
    )
    frame = read_ways(path)
    assert frame["osmWay"].tolist() == [7] and frame.crs.to_epsg() == 4326


def test_a_reach_takes_the_name_of_the_ways_beside_most_of_it():
    named = osm_names(reaches(), ways(), {TAKEN})
    assert named == {
        UPPER: OsmName("Suran River", (1001,)),
        LOWER: OsmName("Suran River", (1002,)),
    }


def test_neighbouring_reaches_of_one_name_are_one_river_from_source_to_mouth():
    named = {UPPER: OsmName("Suran River", (1001,)), LOWER: OsmName("Suran River", (1002,))}
    rivers = osm_rivers(network_of(reaches()), named, {UPPER: [[449, 0.0]], LOWER: [[449, 0.0]]})
    assert rivers == [
        {
            "name": "Suran River",
            "refs": ["way/1001", "way/1002"],
            "mainRiv": LOWER,
            "reachIds": [UPPER, LOWER],
            "districtLgds": [449],
        }
    ]


def test_build_names_writes_both_files_and_a_summary(tmp_path):
    reaches().to_parquet(tmp_path / REACHES_FILE, index=False)
    hits = pd.DataFrame([[UPPER, 449, 0.0], [LOWER, 449, 0.0], [TAKEN, 450, 0.0]], columns=HIT_COLUMNS)
    hits.to_parquet(tmp_path / REACH_DISTRICTS_FILE, index=False)
    entity = "http://www.wikidata.org/entity/"

    def ask(query: str) -> bytes:
        if "pq:P518" in query:
            rows = [{"item": entity + "Q9", "part": entity + "Q1233637", "coord": "Point(72.1 23.0)"}]
        else:
            rows = [{"item": entity + "Q9", "label": "Taken River"}]
        bindings = [{key: {"type": "literal", "value": value} for key, value in row.items()} for row in rows]
        return json.dumps({"results": {"bindings": bindings}}).encode("utf-8")

    summary = build_names(tmp_path, scratch=tmp_path, ask=ask, ways=lambda scratch: OsmWays(ways(), "0" * 64))
    wikidata = json.loads((tmp_path / WIKIDATA_FILE).read_text(encoding="utf-8"))
    osm = json.loads((tmp_path / OSM_FILE).read_text(encoding="utf-8"))
    assert wikidata["schemaVersion"] == 1 and wikidata["dataset"]["code"] == "WIKIDATA_RIVER_NAMES"
    assert [river["reachIds"] for river in wikidata["rivers"]] == [[TAKEN]]
    assert osm["dataset"]["attribution"] == "© OpenStreetMap contributors" and osm["dataset"]["sha256"] == "0" * 64
    assert [(river["name"], river["reachIds"]) for river in osm["rivers"]] == [("Suran River", [UPPER, LOWER])]
    assert summary == json.loads((tmp_path / SUMMARY_FILE).read_text(encoding="utf-8"))
    assert (summary["wikidataRivers"], summary["osmRivers"], summary["osmReaches"]) == (1, 1, 2)


def test_the_river_names_command_reports_what_it_named(monkeypatch, tmp_path, capsys):
    summary = {"wikidataRivers": 3, "wikidataReaches": 40, "osmRivers": 7, "osmReaches": 90}
    monkeypatch.setattr(river_names_files, "build_names", lambda rivers, scratch: summary)
    assert main(["river-names", "--rivers", str(tmp_path), "--scratch", str(tmp_path)]) == 0
    shown = capsys.readouterr().out
    assert "3 rivers named from Wikidata over 40 reaches, 7 from OpenStreetMap over 90 reaches" in shown
