import datetime as dt
import hashlib
import json
import re
from pathlib import Path

import geopandas as gpd
import pandas as pd
import shapely

from geo_etl.catalog import HYDRORIVERS
from geo_etl.districts import load_districts
from geo_etl.layers.hydrorivers import cached_archive, shapefile_member
from geo_etl.river_districts import REACH_DISTRICTS_FILE, districts_by_reach, reach_districts
from geo_etl.topology import SIMPLIFY_DEGREES, basin_topology, encoded

LINE_UPLAND_MIN_SKM = 100
STRAHLER_MAX = 15
OUTLET = 0
SOURCE_FIELDS = {
    "HYRIV_ID": "hyrivId",
    "NEXT_DOWN": "nextDown",
    "MAIN_RIV": "mainRiv",
    "ORD_STRA": "ordStra",
    "UPLAND_SKM": "uplandSkm",
    "DIS_AV_CMS": "disAvCms",
    "LENGTH_KM": "lengthKm",
}
REACH_COLUMNS = [*SOURCE_FIELDS.values(), "geometry"]
REACHES_FILE = "river_reaches.parquet"
BASINS_FILE = "river_basins.json"
TOPOLOGY_DIR = "topology"
TOPOLOGY_PREFIX = "media/rivers"
TOPOLOGY_SUBJECT = "HydroRIVERS-1-0"
EDITION_PATTERN = re.compile(r"[A-Za-z0-9-]+")
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
PROBLEMS_SHOWN = 20


class RiverNetworkError(RuntimeError):
    def __init__(self, problems: list[str]) -> None:
        super().__init__(f"{len(problems)} river network problems: " + "; ".join(problems[:PROBLEMS_SHOWN]))
        self.problems = problems


def topology_file_name(main_riv: int) -> str:
    if main_riv < 1:
        raise ValueError(f"a river topology is filed under its outlet reach id, not {main_riv}")
    return f"KalaVigyan_Dataset_{TOPOLOGY_SUBJECT}_River-Topology_Basin-{main_riv}.json"


def topology_key(edition: str, main_riv: int, sha256: str) -> str:
    if not EDITION_PATTERN.fullmatch(edition):
        raise ValueError(f"a river topology key needs an ASCII edition, not {edition!r}")
    if not SHA256_PATTERN.fullmatch(sha256):
        raise ValueError(f"a river topology key is filed under its content's SHA-256, not {sha256!r}")
    return f"{TOPOLOGY_PREFIX}/{edition}/{main_riv}/{sha256}/{topology_file_name(main_riv)}"


def read_reaches(archive: Path) -> gpd.GeoDataFrame:
    member = shapefile_member(archive)
    frame = gpd.read_file(
        f"zip://{archive.as_posix()}!{member}",
        columns=list(SOURCE_FIELDS),
        where=f"UPLAND_SKM >= {LINE_UPLAND_MIN_SKM}",
    )
    frame = frame.set_crs("EPSG:4326", allow_override=True).rename(columns=SOURCE_FIELDS)
    return single_lines(frame[REACH_COLUMNS])


def single_lines(frame: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    geometry = frame.geometry.to_numpy()
    multi = shapely.get_type_id(geometry) == shapely.GeometryType.MULTILINESTRING
    if multi.any():
        geometry = geometry.copy()
        geometry[multi] = shapely.line_merge(geometry[multi])
    return frame.set_geometry(gpd.GeoSeries(geometry, index=frame.index, crs=frame.crs))


def basins_crossing(reaches: gpd.GeoDataFrame, districts: gpd.GeoDataFrame) -> set[int]:
    joined = gpd.sjoin(reaches[["mainRiv", "geometry"]], districts[["geometry"]], predicate="intersects")
    return {int(v) for v in joined["mainRiv"].unique()}


def india_reaches(reaches: gpd.GeoDataFrame, districts: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    kept = reaches[reaches["mainRiv"].isin(basins_crossing(reaches, districts))]
    return kept.sort_values(["mainRiv", "hyrivId"], kind="stable").reset_index(drop=True)


def network_problems(reaches: pd.DataFrame) -> list[str]:
    ids = reaches["hyrivId"].astype("int64")
    problems = [f"reach {rid} is listed twice" for rid in sorted(set(ids[ids.duplicated()]))]
    down = dict(zip(ids, reaches["nextDown"].astype("int64"), strict=True))
    basin = dict(zip(ids, reaches["mainRiv"].astype("int64"), strict=True))
    for rid, next_down in down.items():
        problems.extend(_reach_problems(rid, next_down, basin))
    problems.extend(_measure_problems(reaches))
    problems.extend(f"reach {rid} flows in a cycle" for rid in cycle_members(down))
    return problems


def _reach_problems(rid: int, next_down: int, basin: dict[int, int]) -> list[str]:
    if next_down == rid:
        return [f"reach {rid} flows into itself"]
    if (next_down == OUTLET) != (rid == basin[rid]):
        return [f"reach {rid} ends its river exactly when it is the river's outlet"]
    if next_down != OUTLET and next_down not in basin:
        return [f"reach {rid} flows into {next_down}, which is not kept"]
    if next_down != OUTLET and basin[next_down] != basin[rid]:
        return [f"reach {rid} of river {basin[rid]} flows into {next_down} of river {basin[next_down]}"]
    return []


def _measure_problems(reaches: pd.DataFrame) -> list[str]:
    rules = {
        "ordStra": ~reaches["ordStra"].between(1, STRAHLER_MAX),
        "uplandSkm": ~(reaches["uplandSkm"] >= 0),
        "disAvCms": ~(reaches["disAvCms"] >= 0),
        "lengthKm": ~(reaches["lengthKm"] > 0),
    }
    problems = [
        f"reach {int(rid)} has {column} {reaches.loc[index, column]}"
        for column, broken in rules.items()
        for index, rid in reaches.loc[broken, "hyrivId"].items()
    ]
    if "geometry" in reaches:
        lines = reaches.geometry.to_numpy()
        broken = (shapely.get_type_id(lines) != shapely.GeometryType.LINESTRING) | (shapely.get_num_points(lines) < 2)
        problems.extend(f"reach {int(rid)} is not one line" for rid in reaches.loc[broken, "hyrivId"])
    return problems


def cycle_members(down: dict[int, int]) -> list[int]:
    settled: set[int] = {OUTLET}
    looped: set[int] = set()
    for start in down:
        walk: dict[int, int] = {}
        here = start
        while here not in settled and here in down and here not in walk:
            walk[here] = len(walk)
            here = down[here]
        if here in walk:
            looped.update(list(walk)[walk[here] :])
        settled.update(walk)
    return sorted(looped)


def basin_entries(reaches: gpd.GeoDataFrame, hits: pd.DataFrame, out: Path) -> list[dict]:
    folder = out / TOPOLOGY_DIR
    folder.mkdir(parents=True, exist_ok=True)
    districts_of = districts_by_reach(hits)
    entries = []
    for main_riv, group in reaches.groupby("mainRiv", sort=True):
        body = encoded(basin_topology(group, districts_of))
        name = f"{int(main_riv)}.json"
        (folder / name).write_bytes(body)
        entries.append(
            {
                "mainRiv": int(main_riv),
                "reaches": int(len(group)),
                "file": f"{TOPOLOGY_DIR}/{name}",
                "sha256": hashlib.sha256(body).hexdigest(),
                "bytes": len(body),
            }
        )
    return entries


def write_rivers(reaches: gpd.GeoDataFrame, hits: pd.DataFrame, out: Path, *, retrieved_at: dt.datetime) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    reaches.to_parquet(out / REACHES_FILE, index=False)
    hits.to_parquet(out / REACH_DISTRICTS_FILE, index=False)
    manifest = {
        "generatedAt": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "dataset": HYDRORIVERS.as_row() | {"retrievedAt": retrieved_at.isoformat(timespec="seconds")},
        "uplandMinSkm": LINE_UPLAND_MIN_SKM,
        "simplifyDegrees": SIMPLIFY_DEGREES,
        "reaches": int(len(reaches)),
        "reachDistricts": int(len(hits)),
        "basins": basin_entries(reaches, hits, out),
    }
    (out / BASINS_FILE).write_text(json.dumps(manifest, indent=1), encoding="utf-8")
    return manifest


def build(out: Path, *, cache: Path) -> dict:
    archive = cached_archive(cache)
    retrieved_at = dt.datetime.now(dt.UTC)
    districts = load_districts()
    reaches = india_reaches(read_reaches(archive), districts)
    problems = network_problems(reaches)
    if problems:
        raise RiverNetworkError(problems)
    return write_rivers(reaches, reach_districts(reaches, districts), out, retrieved_at=retrieved_at)
