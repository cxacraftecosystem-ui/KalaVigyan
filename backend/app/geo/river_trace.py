from __future__ import annotations

from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass

from pydantic import ValidationError

from app.core.errors import AppError
from app.research.rivers import HYDRORIVERS_DATASET_CODE, MOUTH, RiverTrace, trace_problems

__all__ = [
    "TRACE_REACHES_MAX",
    "DistrictHit",
    "ReachLink",
    "RiverNetworkError",
    "districts_in_path_order",
    "river_trace",
    "traced_reach_ids",
]

TRACE_REACHES_MAX = 10_000
PROBLEMS_SHOWN = 5


class RiverNetworkError(AppError):
    pass


@dataclass(frozen=True)
class ReachLink:
    hyriv_id: int
    next_down: int
    main_riv: int
    upland_skm: float


@dataclass(frozen=True)
class DistrictHit:
    position: int
    district_lgd: int
    entry: float


def traced_reach_ids(start: int, links: Mapping[int, ReachLink], *, named: Collection[int] = ()) -> list[int]:
    if start not in links:
        raise RiverNetworkError(f"reach {start} is not stored")
    above = _main_stem_above(start, _largest_upstream(links, frozenset(named)))
    below = _downstream_of(start, links)
    path = [*reversed(above), start, *below]
    if len(path) > TRACE_REACHES_MAX:
        raise RiverNetworkError(f"the river through reach {start} runs past {TRACE_REACHES_MAX} reaches")
    if len(set(path)) != len(path):
        raise RiverNetworkError(f"the river through reach {start} meets itself")
    return path


def districts_in_path_order(hits: Iterable[DistrictHit]) -> list[int]:
    ordered = sorted(hits, key=lambda hit: (hit.position, hit.entry, hit.district_lgd))
    return list(dict.fromkeys(hit.district_lgd for hit in ordered))


def river_trace(path: list[int], links: Mapping[int, ReachLink], district_lgds: list[int]) -> RiverTrace:
    try:
        trace = RiverTrace(
            dataset_code=HYDRORIVERS_DATASET_CODE,
            main_riv=links[path[-1]].main_riv,
            reach_ids=path,
            district_lgds=district_lgds,
        )
    except ValidationError as error:
        raise RiverNetworkError(
            f"the river ending at reach {path[-1]} is off its contract: {error}"
        ) from error
    problems = trace_problems(trace, links)
    if problems:
        raise RiverNetworkError("; ".join(problems[:PROBLEMS_SHOWN]))
    return trace


def _largest_upstream(links: Mapping[int, ReachLink], named: frozenset[int]) -> dict[int, ReachLink]:
    largest: dict[int, ReachLink] = {}
    for link in links.values():
        if link.next_down == MOUTH:
            continue
        held = largest.get(link.next_down)
        if held is None or _climb_rank(link, named) > _climb_rank(held, named):
            largest[link.next_down] = link
    return largest


def _climb_rank(link: ReachLink, named: frozenset[int]) -> tuple[bool, float, int]:
    return link.hyriv_id in named, link.upland_skm, -link.hyriv_id


def _main_stem_above(start: int, largest: Mapping[int, ReachLink]) -> list[int]:
    path: list[int] = []
    seen = {start}
    here = start
    while (link := largest.get(here)) is not None:
        if link.hyriv_id in seen:
            raise RiverNetworkError(f"the reaches above {start} flow in a cycle through {link.hyriv_id}")
        if len(path) >= TRACE_REACHES_MAX:
            raise RiverNetworkError(f"the river above reach {start} runs past {TRACE_REACHES_MAX} reaches")
        path.append(link.hyriv_id)
        seen.add(link.hyriv_id)
        here = link.hyriv_id
    return path


def _downstream_of(start: int, links: Mapping[int, ReachLink]) -> list[int]:
    path: list[int] = []
    seen = {start}
    here = links[start]
    while here.next_down != MOUTH:
        found = links.get(here.next_down)
        if found is None:
            raise RiverNetworkError(f"reach {here.hyriv_id} flows into {here.next_down}, which is not stored")
        if found.hyriv_id in seen:
            raise RiverNetworkError(f"the reaches below {start} flow in a cycle through {found.hyriv_id}")
        if len(path) >= TRACE_REACHES_MAX:
            raise RiverNetworkError(f"the river below reach {start} runs past {TRACE_REACHES_MAX} reaches")
        path.append(found.hyriv_id)
        seen.add(found.hyriv_id)
        here = found
    return path
