from collections.abc import Sequence
from dataclasses import dataclass

import geopandas as gpd
import numpy as np
import shapely

OUTLET = 0
EARTH_RADIUS_KM = 6371.0088


@dataclass(frozen=True)
class Network:
    ids: np.ndarray
    starts: np.ndarray
    ends: np.ndarray
    outlets: np.ndarray
    next_down: dict[int, int]
    inflows: dict[int, tuple[int, ...]]
    upland: dict[int, float]
    main_riv: dict[int, int]
    position: dict[int, int]

    def headwater(self, reach: int) -> bool:
        return not self.inflows.get(reach)

    def starts_of(self, reaches: Sequence[int]) -> np.ndarray:
        return self.starts[[self.position[reach] for reach in reaches]]

    def ends_of(self, reaches: Sequence[int]) -> np.ndarray:
        return self.ends[[self.position[reach] for reach in reaches]]


def network_of(reaches: gpd.GeoDataFrame) -> Network:
    ids = reaches["hyrivId"].astype("int64").to_numpy()
    lines = reaches.geometry.to_numpy()
    starts = shapely.get_coordinates(shapely.get_point(lines, 0))
    ends = shapely.get_coordinates(shapely.get_point(lines, -1))
    next_down = dict(zip(ids.tolist(), reaches["nextDown"].astype("int64").tolist(), strict=True))
    inflows: dict[int, list[int]] = {}
    for reach, down in next_down.items():
        if down != OUTLET:
            inflows.setdefault(down, []).append(reach)
    return Network(
        ids=ids,
        starts=starts,
        ends=ends,
        outlets=np.array([down == OUTLET for down in next_down.values()], dtype=bool),
        next_down=next_down,
        inflows={reach: tuple(sorted(found)) for reach, found in inflows.items()},
        upland=dict(zip(ids.tolist(), reaches["uplandSkm"].astype("float64").tolist(), strict=True)),
        main_riv=dict(zip(ids.tolist(), reaches["mainRiv"].astype("int64").tolist(), strict=True)),
        position={reach: index for index, reach in enumerate(ids.tolist())},
    )


def km_from(points: np.ndarray, lon: float, lat: float) -> np.ndarray:
    lon1, lat1 = np.radians(points[:, 0]), np.radians(points[:, 1])
    lon2, lat2 = np.radians(lon), np.radians(lat)
    a = np.sin((lat2 - lat1) / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin((lon2 - lon1) / 2) ** 2
    return 2 * EARTH_RADIUS_KM * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def nearest_km(points: np.ndarray, targets: Sequence[tuple[float, float]]) -> np.ndarray:
    found = np.full(len(points), np.inf)
    for lon, lat in targets:
        found = np.minimum(found, km_from(points, lon, lat))
    return found


def upstream_of(network: Network, reach: int) -> list[int]:
    found, frontier = [reach], [reach]
    while frontier:
        above = [inflow for here in frontier for inflow in network.inflows.get(here, ())]
        found.extend(above)
        frontier = above
    return found


def path_down(network: Network, start: int, stop: int) -> list[int] | None:
    path, here = [start], start
    while here != stop:
        here = network.next_down.get(here, OUTLET)
        if here == OUTLET or here in path:
            return None
        path.append(here)
    return path


def main_stem_above(network: Network, reach: int) -> list[int]:
    path, here = [reach], reach
    while network.inflows.get(here):
        here = max(network.inflows[here], key=lambda inflow: (network.upland[inflow], -inflow))
        path.append(here)
    return list(reversed(path))


def downstream_order(network: Network, reaches: Sequence[int]) -> list[int]:
    held = set(reaches)
    hops = {reach: _hops_within(network, reach, held) for reach in reaches}
    return sorted(reaches, key=lambda reach: (-hops[reach], reach))


def _hops_within(network: Network, reach: int, held: set[int]) -> int:
    count, here = 0, network.next_down.get(reach, OUTLET)
    while here in held:
        count += 1
        here = network.next_down.get(here, OUTLET)
    return count
