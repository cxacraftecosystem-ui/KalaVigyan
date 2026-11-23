from collections.abc import Mapping

import geopandas as gpd
import numpy as np
import pandas as pd
import shapely

ENTRY_DECIMALS = 4
HIT_COLUMNS = ["hyrivId", "districtLgd", "entry"]
HIT_TYPES = {"hyrivId": "int64", "districtLgd": "int64", "entry": "float64"}
REACH_DISTRICTS_FILE = "river_reach_districts.parquet"
POINT = shapely.GeometryType.POINT
LINE = shapely.GeometryType.LINESTRING
NESTED = (
    shapely.GeometryType.MULTIPOINT,
    shapely.GeometryType.MULTILINESTRING,
    shapely.GeometryType.MULTIPOLYGON,
    shapely.GeometryType.GEOMETRYCOLLECTION,
)


def reach_districts(reaches: gpd.GeoDataFrame, districts: gpd.GeoDataFrame) -> pd.DataFrame:
    pairs = gpd.sjoin(reaches[["hyrivId", "geometry"]], districts[["districtLgd", "geometry"]], predicate="intersects")
    if pairs.empty:
        return pd.DataFrame(columns=HIT_COLUMNS).astype(HIT_TYPES)
    shapes = districts.geometry.loc[pairs["index_right"]].to_numpy()
    entries = [entry_of(line, shape) for line, shape in zip(pairs.geometry.to_numpy(), shapes, strict=True)]
    hits = pd.DataFrame(
        {
            "hyrivId": pairs["hyrivId"].to_numpy(),
            "districtLgd": pairs["districtLgd"].to_numpy(),
            "entry": entries,
        }
    ).astype(HIT_TYPES)
    hits = hits[hits["entry"].notna()]
    hits = hits.groupby(["hyrivId", "districtLgd"], as_index=False)["entry"].min()
    return hits.sort_values(["hyrivId", "entry", "districtLgd"], kind="stable").reset_index(drop=True)


def entry_of(line: shapely.LineString, shape: shapely.Geometry) -> float:
    starts = [_start(part) for part in _parts(shapely.intersection(line, shape))]
    starts = [start for start in starts if start is not None]
    if not starts:
        return float("nan")
    located = shapely.line_locate_point(line, np.array(starts, dtype=object), normalized=True)
    return round(float(np.min(located)), ENTRY_DECIMALS)


def _start(part: shapely.Geometry) -> shapely.Geometry | None:
    kind = shapely.get_type_id(part)
    if kind == POINT:
        return part
    if kind == LINE:
        return shapely.get_point(part, 0)
    return None


def _parts(geometry: shapely.Geometry) -> list[shapely.Geometry]:
    found: list[shapely.Geometry] = []
    for part in shapely.get_parts(geometry):
        found.extend(_parts(part) if shapely.get_type_id(part) in NESTED else [part])
    return found


def districts_by_reach(hits: pd.DataFrame) -> Mapping[int, list[list]]:
    ordered = hits.sort_values(["hyrivId", "entry", "districtLgd"], kind="stable")
    found: dict[int, list[list]] = {}
    for hyriv_id, lgd, entry in ordered[HIT_COLUMNS].itertuples(index=False, name=None):
        found.setdefault(int(hyriv_id), []).append([int(lgd), round(float(entry), ENTRY_DECIMALS)])
    return found
