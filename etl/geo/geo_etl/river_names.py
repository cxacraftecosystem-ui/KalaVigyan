from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, replace

import numpy as np

from geo_etl.river_network import OUTLET, Network, main_stem_above, nearest_km, path_down, upstream_of
from geo_etl.wikidata_rivers import WikidataRiver

MOUTH_KM = 10.0
OUTLET_MOUTH_KM = 30.0
SOURCE_KM = 30.0
AREA_RATIO = 0.5
TIE_DECIMALS = 3
NO_MOUTH = "no reach ends within the mouth distance"
NO_COURSE = "no reach near its mouth runs its course"
TIED = "two reaches run its course equally"
WRONG_BASIN = "its last reach does not flow into the river its mouth names"


@dataclass(frozen=True)
class Course:
    item: str
    name: str
    reaches: tuple[int, ...]
    mouth_km: float
    score: float

    def rank(self) -> tuple[float, float]:
        return round(self.mouth_km, TIE_DECIMALS), round(self.score, TIE_DECIMALS)


@dataclass(frozen=True)
class Matches:
    courses: dict[str, Course]
    refused: dict[str, str]


def wikidata_matches(network: Network, rivers: Iterable[WikidataRiver]) -> Matches:
    listed = list(rivers)
    courses: dict[str, Course] = {}
    refused: dict[str, str] = {}
    for river in listed:
        found = course_of(network, river)
        if isinstance(found, Course):
            courses[river.item] = found
        else:
            refused[river.item] = found
    joined: dict[str, Course] = {}
    for river in listed:
        if river.item not in courses:
            continue
        found = into_its_mouth(network, courses, river)
        if found is None:
            refused[river.item] = WRONG_BASIN
        else:
            joined[river.item] = found
    return Matches(joined, refused)


def course_of(network: Network, river: WikidataRiver) -> Course | str:
    distance = nearest_km(network.ends, river.mouths)
    near = np.flatnonzero((distance <= MOUTH_KM) | (network.outlets & (distance <= OUTLET_MOUTH_KM)))
    if not len(near):
        return NO_MOUTH
    unique = len(near) == 1 and distance[near[0]] <= MOUTH_KM
    found = [
        course
        for index in near
        if (course := candidate(network, river, int(network.ids[index]), float(distance[index]), unique))
    ]
    if not found:
        return NO_COURSE
    found.sort(key=Course.rank)
    if len(found) > 1 and found[0].rank() == found[1].rank():
        return TIED
    return found[0]


def candidate(network: Network, river: WikidataRiver, reach: int, mouth_km: float, unique: bool) -> Course | None:
    if river.sources:
        return _from_source(network, river, reach, mouth_km)
    areas = [area for area in river.areas_km2 if area > 0]
    if areas:
        ratio = min(abs(network.upland[reach] - area) / area for area in areas)
        if ratio > AREA_RATIO:
            return None
        return Course(river.item, river.label, tuple(main_stem_above(network, reach)), mouth_km, ratio)
    if unique and network.next_down[reach] == OUTLET:
        return Course(river.item, river.label, tuple(main_stem_above(network, reach)), mouth_km, 0.0)
    return None


def _from_source(network: Network, river: WikidataRiver, reach: int, mouth_km: float) -> Course | None:
    heads = [above for above in upstream_of(network, reach) if network.headwater(above)]
    distance = nearest_km(network.starts_of(heads), river.sources)
    best = int(np.argmin(distance))
    if distance[best] > SOURCE_KM:
        return None
    path = path_down(network, heads[best], reach)
    if path is None:
        return None
    return Course(river.item, river.label, tuple(path), mouth_km, float(distance[best]))


def into_its_mouth(network: Network, courses: Mapping[str, Course], river: WikidataRiver) -> Course | None:
    course = courses[river.item]
    into = [courses[item] for item in river.mouth_items if item in courses and item != river.item]
    if not into:
        return course
    return next((found for other in into if (found := joined_course(network, course, other, river))), None)


def joined_course(network: Network, course: Course, into: Course, river: WikidataRiver) -> Course | None:
    path = list(course.reaches)
    while True:
        last = path[-1]
        down = network.next_down[last]
        if last in into.reaches or down in into.reaches:
            return replace(course, reaches=tuple(path))
        if down == OUTLET or nearest_km(network.ends_of([down]), river.mouths)[0] > MOUTH_KM:
            return None
        path.append(down)


def named_reaches(courses: Mapping[str, Course]) -> dict[int, str]:
    claims: dict[int, list[Course]] = {}
    for course in courses.values():
        for reach in course.reaches:
            claims.setdefault(reach, []).append(course)
    named: dict[int, str] = {}
    for reach, found in claims.items():
        shortest = min(len(course.reaches) for course in found)
        winners = [course for course in found if len(course.reaches) == shortest]
        if len(winners) == 1:
            named[reach] = winners[0].item
    return named


def wikidata_rivers(
    network: Network, courses: Mapping[str, Course], districts_of: Mapping[int, list[list]]
) -> list[dict]:
    named = named_reaches(courses)
    rivers = []
    for item, course in sorted(courses.items()):
        reaches = [reach for reach in course.reaches if named.get(reach) == item]
        if reaches:
            rivers.append(river_row(network, course.name, [item], reaches, districts_of))
    return rivers


def river_row(
    network: Network, name: str, refs: Sequence[str], reaches: Sequence[int], districts_of: Mapping[int, list[list]]
) -> dict:
    return {
        "name": name,
        "refs": list(refs),
        "mainRiv": network.main_riv[reaches[-1]],
        "reachIds": list(reaches),
        "districtLgds": districts_along(reaches, districts_of),
    }


def districts_along(reaches: Sequence[int], districts_of: Mapping[int, list[list]]) -> list[int]:
    found = [int(lgd) for reach in reaches for lgd, _ in districts_of.get(reach, [])]
    return list(dict.fromkeys(found))
