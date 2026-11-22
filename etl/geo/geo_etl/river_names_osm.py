from collections import Counter
from collections.abc import Collection, Mapping
from dataclasses import dataclass

import geopandas as gpd
import numpy as np
import shapely

from geo_etl.districts import INDIA_LCC
from geo_etl.river_names import river_row
from geo_etl.river_network import Network, downstream_order

SAMPLE_M = 500.0
SAMPLES_MIN = 3
NEAR_M = 1000.0
SHARE_MIN = 0.8


@dataclass(frozen=True)
class OsmName:
    name: str
    ways: tuple[int, ...]


def osm_names(reaches: gpd.GeoDataFrame, ways: gpd.GeoDataFrame, taken: Collection[int]) -> dict[int, OsmName]:
    free = reaches[~reaches["hyrivId"].isin(list(taken))]
    if free.empty or ways.empty:
        return {}
    lines = free.to_crs(INDIA_LCC).geometry.to_numpy()
    placed = ways.to_crs(INDIA_LCC)
    counts = np.maximum(SAMPLES_MIN, np.ceil(shapely.length(lines) / SAMPLE_M)).astype("int64")
    owner = np.repeat(np.arange(len(lines)), counts)
    fractions = np.concatenate([(np.arange(count) + 0.5) / count for count in counts])
    points = shapely.line_interpolate_point(lines[owner], fractions, normalized=True)
    tree = shapely.STRtree(placed.geometry.to_numpy())
    point_index, way_index = tree.query_nearest(points, max_distance=NEAR_M, all_matches=False)
    names = placed["name"].to_numpy()[way_index]
    way_ids = placed["osmWay"].to_numpy()[way_index]
    samples: dict[int, list[tuple[str, int]]] = {}
    for at, name, way in zip(owner[point_index], names, way_ids, strict=True):
        samples.setdefault(int(at), []).append((str(name), int(way)))
    ids = free["hyrivId"].astype("int64").to_numpy()
    return {
        int(ids[at]): found
        for at, sampled in samples.items()
        if (found := _majority(sampled, int(counts[at]))) is not None
    }


def _majority(sampled: list[tuple[str, int]], count: int) -> OsmName | None:
    name, held = Counter(name for name, _ in sampled).most_common(1)[0]
    if held / count < SHARE_MIN:
        return None
    return OsmName(name=name, ways=tuple(sorted({way for found, way in sampled if found == name})))


def osm_rivers(network: Network, named: Mapping[int, OsmName], districts_of: Mapping[int, list[list]]) -> list[dict]:
    rivers = []
    for members in _same_named_runs(network, named):
        ordered = downstream_order(network, members)
        ways = sorted({way for reach in ordered for way in named[reach].ways})
        refs = [f"way/{way}" for way in ways]
        rivers.append(river_row(network, named[ordered[0]].name, refs, ordered, districts_of))
    return sorted(rivers, key=lambda river: (river["mainRiv"], river["name"], river["reachIds"][0]))


def _same_named_runs(network: Network, named: Mapping[int, OsmName]) -> list[list[int]]:
    parent = {reach: reach for reach in named}

    def root(reach: int) -> int:
        while parent[reach] != reach:
            parent[reach] = parent[parent[reach]]
            reach = parent[reach]
        return reach

    for reach, found in named.items():
        down = network.next_down.get(reach)
        if down in named and named[down].name == found.name:
            parent[root(reach)] = root(down)
    runs: dict[int, list[int]] = {}
    for reach in named:
        runs.setdefault(root(reach), []).append(reach)
    return [sorted(members) for members in runs.values()]
