import hashlib
import json

import geopandas as gpd
import pytest
from shapely.geometry import LineString

from geo_etl.river_names import (
    NO_COURSE,
    NO_MOUTH,
    TIED,
    WRONG_BASIN,
    Course,
    named_reaches,
    wikidata_matches,
    wikidata_rivers,
)
from geo_etl.river_network import km_from, main_stem_above, network_of, upstream_of
from geo_etl.wikidata_rivers import RIVER_MOUTH, RIVER_SOURCE, WikidataRiver, fetch_rivers

EAST_HEAD, WEST_HEAD, MIDDLE, OUTLET_A, OUTLET_B = 501, 502, 503, 500, 600
CONFLUENCE = (70.10, 23.90)
REACHES = [
    (EAST_HEAD, MIDDLE, OUTLET_A, 150.0, [(70.00, 24.00), CONFLUENCE]),
    (WEST_HEAD, MIDDLE, OUTLET_A, 300.0, [(70.30, 24.00), CONFLUENCE]),
    (MIDDLE, OUTLET_A, OUTLET_A, 500.0, [CONFLUENCE, (70.20, 23.70)]),
    (OUTLET_A, 0, OUTLET_A, 600.0, [(70.20, 23.70), (70.30, 23.50)]),
    (OUTLET_B, 0, OUTLET_B, 200.0, [(71.00, 23.00), (71.10, 22.90)]),
]
DISTRICTS_OF = {EAST_HEAD: [[449, 0.0]], MIDDLE: [[449, 0.0], [450, 0.5]], OUTLET_A: [[450, 0.0]], OUTLET_B: []}


def reaches(rows=REACHES) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(
        [
            {
                "hyrivId": rid,
                "nextDown": down,
                "mainRiv": main,
                "ordStra": 2,
                "uplandSkm": upland,
                "disAvCms": 1.0,
                "lengthKm": 20.0,
                "geometry": LineString(coords),
            }
            for rid, down, main, upland, coords in rows
        ],
        geometry="geometry",
        crs="EPSG:4326",
    )


def river(item, label, mouths, *, sources=(), into=(), areas=()) -> WikidataRiver:
    return WikidataRiver(item, label, tuple(mouths), tuple(sources), tuple(into), tuple(areas))


ALPHA = river("Q1", "Alpha River", [(70.30, 23.50)], sources=[(70.00, 24.02)])
BETA = river("Q2", "Beta Nadi", [CONFLUENCE], sources=[(70.31, 24.01)], into=["Q1"])
GAMMA = river("Q3", "Gamma", [(71.10, 22.90)], areas=[210.0])
FAR = river("Q4", "Delta", [(80.0, 20.0)])
ASTRAY = river("Q5", "Epsilon", [(70.30, 23.50)], areas=[600.0], into=["Q3"])
EVEN = river("Q6", "Zeta", [CONFLUENCE], areas=[225.0])


def test_distances_are_great_circle_kilometres():
    network = network_of(reaches())
    assert km_from(network.starts[:1], 70.00, 24.02)[0] == pytest.approx(6371.0088 * 0.02 * 3.141592653589793 / 180)


def test_the_network_walks_upstream_and_up_the_largest_inflow():
    network = network_of(reaches())
    assert sorted(upstream_of(network, OUTLET_A)) == [OUTLET_A, EAST_HEAD, WEST_HEAD, MIDDLE]
    assert main_stem_above(network, OUTLET_A) == [WEST_HEAD, MIDDLE, OUTLET_A]


def test_each_river_is_matched_by_its_mouth_then_its_source_or_area_and_its_basin():
    matches = wikidata_matches(network_of(reaches()), [ALPHA, BETA, GAMMA, FAR, ASTRAY, EVEN])
    assert {item: course.reaches for item, course in matches.courses.items()} == {
        "Q1": (EAST_HEAD, MIDDLE, OUTLET_A),
        "Q2": (WEST_HEAD,),
        "Q3": (OUTLET_B,),
    }
    assert matches.refused == {"Q4": NO_MOUTH, "Q5": WRONG_BASIN, "Q6": TIED}
    assert matches.courses["Q1"].score == pytest.approx(2.224, abs=0.001)
    assert matches.courses["Q3"].score == pytest.approx(10.0 / 210.0)


def test_a_river_s_outlet_may_lie_farther_from_its_mouth_only_with_its_course_stated():
    offshore = river("Q7", "Offshore", [(70.30, 23.32)], sources=[(70.00, 24.02)])
    bare = river("Q8", "Bare", [(70.30, 23.32)])
    matches = wikidata_matches(network_of(reaches()), [offshore, bare])
    assert matches.courses["Q7"].reaches == (EAST_HEAD, MIDDLE, OUTLET_A)
    assert matches.courses["Q7"].mouth_km == pytest.approx(20.0, abs=0.1)
    assert matches.refused == {"Q8": NO_COURSE}


JOINED = (72.02, 23.86)
TWO_REACH_TRIBUTARY = [
    (901, 902, 904, 100.0, [(72.00, 24.00), (72.00, 23.90)]),
    (902, 904, 904, 120.0, [(72.00, 23.90), JOINED]),
    (903, 904, 904, 400.0, [(72.20, 24.00), JOINED]),
    (904, 0, 904, 600.0, [JOINED, (72.10, 23.70)]),
]


def test_a_tributary_ending_short_of_its_river_is_carried_down_to_where_it_joins():
    parent = river("Q20", "Parent", [(72.10, 23.70)], sources=[(72.20, 24.01)])
    tributary = river("Q21", "Tributary", [(72.00, 23.90)], sources=[(72.00, 24.01)], into=["Q20"])
    matches = wikidata_matches(network_of(reaches(TWO_REACH_TRIBUTARY)), [parent, tributary])
    assert matches.courses["Q20"].reaches == (903, 904)
    assert matches.courses["Q21"].reaches == (901, 902)
    assert matches.refused == {}


def test_a_reach_two_rivers_claim_takes_the_shorter_river_s_name_or_none():
    long = Course("Q10", "Long", (1, 2, 3), 0.0, 0.0)
    short = Course("Q11", "Short", (1, 2), 0.0, 0.0)
    twin = Course("Q12", "Twin", (1, 2), 0.0, 0.0)
    assert named_reaches({"Q10": long, "Q11": short}) == {1: "Q11", 2: "Q11", 3: "Q10"}
    assert named_reaches({"Q10": long, "Q11": short, "Q12": twin}) == {3: "Q10"}


def test_matched_rivers_are_written_with_their_basin_and_districts_in_path_order():
    network = network_of(reaches())
    matches = wikidata_matches(network, [ALPHA, BETA, GAMMA])
    assert wikidata_rivers(network, matches.courses, DISTRICTS_OF) == [
        {
            "name": "Alpha River",
            "refs": ["Q1"],
            "mainRiv": OUTLET_A,
            "reachIds": [EAST_HEAD, MIDDLE, OUTLET_A],
            "districtLgds": [449, 450],
        },
        {"name": "Beta Nadi", "refs": ["Q2"], "mainRiv": OUTLET_A, "reachIds": [WEST_HEAD], "districtLgds": []},
        {"name": "Gamma", "refs": ["Q3"], "mainRiv": OUTLET_B, "reachIds": [OUTLET_B], "districtLgds": []},
    ]


def sparql_body(rows: list[dict]) -> bytes:
    wrapped = [{key: {"type": "literal", "value": value} for key, value in row.items()} for row in rows]
    return json.dumps({"results": {"bindings": wrapped}}).encode("utf-8")


ENTITY = "http://www.wikidata.org/entity/"


def test_the_wikidata_answer_keeps_english_named_rivers_with_a_mouth():
    points = sparql_body(
        [
            {"item": ENTITY + "Q1", "part": ENTITY + RIVER_MOUTH, "coord": "Point(72.8132 21.6617)"},
            {"item": ENTITY + "Q1", "part": ENTITY + RIVER_SOURCE, "coord": "Point(81.75 22.666666666)"},
            {"item": ENTITY + "Q2", "part": ENTITY + RIVER_MOUTH, "coord": "Point(70.3 22.6833)"},
            {"item": ENTITY + "Q9", "part": ENTITY + RIVER_SOURCE, "coord": "Point(70.0 23.0)"},
            {
                "item": ENTITY + "Q7",
                "part": ENTITY + RIVER_MOUTH,
                "coord": "<http://www.wikidata.org/entity/Q111> Point(1 2)",
            },
        ]
    )
    facts = sparql_body(
        [
            {"item": ENTITY + "Q1", "label": "Narmada", "mouth": ENTITY + "Q58705", "area": "100000000000.0"},
            {"item": ENTITY + "Q1", "label": "Narmada", "mouth": ENTITY + "Q654010", "area": "100000000000.0"},
            {"item": ENTITY + "Q2", "label": "Und River"},
            {"item": ENTITY + "Q9"},
        ]
    )
    asked: list[str] = []

    def ask(query: str) -> bytes:
        asked.append(query)
        return points if len(asked) == 1 else facts

    answer = fetch_rivers((60.0, 5.0, 100.0, 40.0), ask)
    assert "?lon >= 60.0 && ?lon <= 100.0 && ?lat >= 5.0 && ?lat <= 40.0" in asked[0]
    assert "VALUES ?item { wd:Q1 wd:Q2 wd:Q9 }" in asked[1]
    assert answer.rivers == (
        WikidataRiver(
            "Q1", "Narmada", ((72.8132, 21.6617),), ((81.75, 22.666666666),), ("Q58705", "Q654010"), (100000.0,)
        ),
        WikidataRiver("Q2", "Und River", ((70.3, 22.6833),), (), (), ()),
    )
    assert answer.sha256 == hashlib.sha256(points + facts).hexdigest()
