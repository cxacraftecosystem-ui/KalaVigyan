from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.geo.datasets import region_dataset
from app.research.component_specs_map_parts import MapParts
from app.research.component_specs_science_coded import CodedFigureSpec
from app.research.component_specs_timeline_map import DeclaredTimelineMapSpec
from app.research.datasets import BOUNDARY_CAPTION, BOUNDARY_DATASET_CODE, DatasetRef

from .layer_records import PHYSICAL_FILES, physical_records
from .map_layer_places import held_map_problems, held_water_problems
from .map_layer_store import listed_layers
from .region_records import dataset_records
from .supply_places import PlaceFinder
from .timeline_map_places import found_places

__all__ = [
    "NOT_HELD",
    "NO_BOUNDARY",
    "NO_LAYER_RECORD",
    "NO_RECORD",
    "MapCredits",
    "SpecPlacement",
    "map_credits",
    "placed_spec",
]

NO_BOUNDARY = f"the site holds no {BOUNDARY_DATASET_CODE} record to cite beneath the map"
NOT_HELD = "the site holds no layer named {name!r}: name relief, rivers, minerals or one of its district layers ({held})"
NO_RECORD = "the layer {name} rests on {code}, which the site holds no dataset record for"
NO_LAYER_RECORD = "the layer {name}'s file names no dataset record the map could credit"


@dataclass(frozen=True)
class MapCredits:
    datasets: list[DatasetRef] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SpecPlacement:
    problems: list[str] = field(default_factory=list)
    spec: dict[str, Any] | None = None


async def placed_spec(
    session: AsyncSession, checked: Any, *, finder: PlaceFinder | None = None
) -> SpecPlacement:
    if isinstance(checked, MapParts):
        return SpecPlacement(problems=held_map_problems(checked))
    if isinstance(checked, CodedFigureSpec):
        drawn = checked.map
        return SpecPlacement(problems=held_water_problems(drawn.rivers, drawn.dams) if drawn else [])
    if not isinstance(checked, DeclaredTimelineMapSpec):
        return SpecPlacement()
    found = await found_places(session, checked, finder=finder)
    credits = await map_credits(session, checked.layers)
    problems = [*found.problems, *credits.problems]
    if problems:
        return SpecPlacement(problems=problems)
    places = [place.model_copy(update={"found": found.places[at]}) for at, place in enumerate(checked.places)]
    parts = {"places": places, "datasets": credits.datasets, "boundary_caption": BOUNDARY_CAPTION}
    placed = checked.model_copy(update=parts)
    return SpecPlacement(spec=placed.model_dump(mode="json"))


async def map_credits(session: AsyncSession, layers: Sequence[str]) -> MapCredits:
    listing = await listed_layers(session)
    boundary = listing.boundary
    if boundary is None:
        return MapCredits(problems=[NO_BOUNDARY])
    held = {layer.spec.id: layer.spec.dataset_code for layer in listing.layers}
    credited: dict[str, DatasetRef | None] = {}
    stored: dict[str, str] = {}
    problems: list[str] = []
    for name in layers:
        if name in PHYSICAL_FILES:
            refs = physical_records(name)
            problems += [] if refs else [NO_LAYER_RECORD.format(name=name)]
            credited |= {ref.code: ref for ref in refs if ref.code not in credited}
        elif name in held:
            credited.setdefault(held[name], None)
            stored.setdefault(held[name], name)
        else:
            problems.append(
                NOT_HELD.format(name=name, held=", ".join(sorted(held)) or "no district layer is stored")
            )
    records = await dataset_records(session, stored)
    problems += [
        NO_RECORD.format(name=name, code=code) for code, name in stored.items() if code not in records
    ]
    datasets = [
        region_dataset(boundary),
        *(
            ref if ref is not None else region_dataset(records[code])
            for code, ref in credited.items()
            if ref is not None or code in records
        ),
    ]
    return MapCredits(datasets=datasets, problems=problems)
