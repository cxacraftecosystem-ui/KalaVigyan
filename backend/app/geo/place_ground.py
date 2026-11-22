from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field

from app.research.citations import SourceRef
from app.research.crafts import CraftRef
from app.research.datasets import DatasetRef
from app.research.place_ground import (
    DEPOSIT_RADIUS_KM,
    GROUND_SCHEMA_VERSION,
    Elevation,
    GroundAt,
    GroundPlace,
    GroundReading,
    MapPlaceGround,
    Tally,
    Water,
)
from app.research.why_here import CraftGround, GroundDeposit, GroundFrame, GroundPin, GroundRiver

from .ground_frame import framed, place_box
from .ground_layers import Deposit, GroundLayers
from .ground_materials import CraftMaterial, material_commodities, material_deposits, soil_materials
from .ground_measure import Nearest, elevation_band, haversine_km, nearest_lake, nearest_line, within

__all__ = [
    "ABROAD_REACH_KM",
    "COMMODITIES_SHOWN",
    "DEPOSITS_SHOWN",
    "GroundInputs",
    "LocatedPlace",
    "Measured",
    "Measures",
    "craft_ground",
    "direct_measures",
    "ground_at",
    "map_place_ground",
    "measured",
    "pins_in_reach",
]

ABROAD_REACH_KM = 500
COMMODITIES_SHOWN = 8
DEPOSITS_SHOWN = 160
KM_PLACES = 1
DEGREE_PLACES = 3

Point = tuple[float, float]
Box = tuple[float, float, float, float]


@dataclass(frozen=True)
class Measured:
    elevation: tuple[int | None, int | None]
    river: Nearest | None
    lake: Nearest | None
    deposits: tuple[tuple[Deposit, float], ...]


@dataclass(frozen=True)
class LocatedPlace:
    key: str
    name: str
    roles: tuple[str, ...]
    precision: str
    district: str | None
    district_lgd: int | None
    state: str | None
    longitude: float
    latitude: float
    source_id: str


@dataclass(frozen=True)
class GroundInputs:
    craft: CraftRef
    places: tuple[LocatedPlace, ...]
    materials: tuple[CraftMaterial, ...] = ()
    readings: Mapping[int, tuple[GroundReading, ...]] = field(default_factory=dict)
    datasets: tuple[DatasetRef, ...] = ()
    sources: tuple[SourceRef, ...] = ()
    abroad: tuple[GroundPin, ...] = ()
    rivers: tuple[GroundRiver, ...] = ()


@dataclass(frozen=True)
class Measures:
    layers: GroundLayers
    at: Callable[[Point], Measured]
    frame: Callable[[Box], GroundFrame]


def measured(layers: GroundLayers, point: Point, radius_km: float = DEPOSIT_RADIUS_KM) -> Measured:
    return Measured(
        elevation=elevation_band(point, layers.bands, layers.breaks),
        river=nearest_line(point, layers.rivers),
        lake=nearest_lake(point, layers.lakes),
        deposits=tuple(within(point, layers.deposits, radius_km)),
    )


def direct_measures(layers: GroundLayers) -> Measures:
    return Measures(
        layers=layers, at=lambda point: measured(layers, point), frame=lambda box: framed(layers, box)
    )


def _water(found: Nearest | None, ranked: bool) -> Water | None:
    if found is None:
        return None
    return Water(
        distance_km=round(found.distance_km, KM_PLACES),
        scale_rank=found.rank if ranked else None,
        longitude=round(found.at[0], DEGREE_PLACES),
        latitude=round(found.at[1], DEGREE_PLACES),
    )


def _tallies(keys: Sequence[str], labels: Mapping[str, str], shown: int | None = None) -> list[Tally]:
    counted = sorted(Counter(keys).items(), key=lambda item: (-item[1], labels.get(item[0], item[0])))
    return [Tally(key=key, label=labels.get(key, key), count=count) for key, count in counted[:shown]]


def ground_at(layers: GroundLayers, found: Measured, readings: Sequence[GroundReading]) -> GroundAt:
    classes = {mineral.id: mineral.label for mineral in layers.classes}
    deposits = [deposit for deposit, _ in found.deposits]
    low, high = found.elevation
    return GroundAt(
        elevation=Elevation(low_m=low, high_m=high),
        river=_water(found.river, ranked=True),
        lake=_water(found.lake, ranked=False),
        deposit_classes=_tallies([layers.classes[d.class_index].id for d in deposits], classes),
        commodities=_tallies([name for d in deposits for name in d.commodities], {}, COMMODITIES_SHOWN),
        readings=list(readings),
    )


def _place(inputs: GroundInputs, layers: GroundLayers, place: LocatedPlace, found: Measured) -> GroundPlace:
    readings = inputs.readings.get(place.district_lgd, ()) if place.district_lgd is not None else ()
    return GroundPlace(
        key=place.key,
        name=place.name,
        roles=list(place.roles),
        precision=place.precision,
        district=place.district,
        state=place.state,
        longitude=round(place.longitude, DEGREE_PLACES),
        latitude=round(place.latitude, DEGREE_PLACES),
        source_id=place.source_id,
        ground=ground_at(layers, found, readings),
        materials=material_deposits(inputs.materials, found.deposits),
    )


def _deposits(found: Sequence[Measured], wanted: set[str]) -> list[GroundDeposit]:
    nearest: dict[int, tuple[Deposit, float]] = {}
    for measure in found:
        for deposit, distance in measure.deposits:
            if deposit.dep_id not in nearest or distance < nearest[deposit.dep_id][1]:
                nearest[deposit.dep_id] = (deposit, distance)
    ordered = sorted(nearest.values(), key=lambda item: (item[1], item[0].dep_id))[:DEPOSITS_SHOWN]
    return [
        GroundDeposit(
            dep_id=deposit.dep_id,
            name=deposit.name,
            longitude=deposit.longitude,
            latitude=deposit.latitude,
            class_index=deposit.class_index,
            status=deposit.status,
            commodities=", ".join(deposit.commodities),
            nearest_km=round(distance, KM_PLACES),
            matched=bool(wanted & set(deposit.commodities)),
        )
        for deposit, distance in ordered
    ]


def pins_in_reach(places: Sequence[LocatedPlace], pins: Sequence[GroundPin]) -> list[GroundPin]:
    return [
        pin
        for pin in pins
        if any(
            haversine_km((place.longitude, place.latitude), (pin.longitude, pin.latitude)) <= ABROAD_REACH_KM
            for place in places
        )
    ]


def craft_ground(inputs: GroundInputs, measures: Measures) -> CraftGround | None:
    if not inputs.places:
        return None
    layers = measures.layers
    found = [measures.at((place.longitude, place.latitude)) for place in inputs.places]
    wanted = {name for material in inputs.materials for name in material_commodities(material)}
    abroad = pins_in_reach(inputs.places, inputs.abroad)
    points = [(p.longitude, p.latitude) for p in inputs.places] + [(p.longitude, p.latitude) for p in abroad]
    return CraftGround(
        schema_version=GROUND_SCHEMA_VERSION,
        craft=inputs.craft,
        radius_km=DEPOSIT_RADIUS_KM,
        places=[
            _place(inputs, layers, place, taken) for place, taken in zip(inputs.places, found, strict=True)
        ],
        soil_materials=soil_materials(inputs.materials),
        deposits=_deposits(found, wanted),
        classes=list(layers.classes),
        frame=measures.frame(place_box(points, DEPOSIT_RADIUS_KM)),
        layers=list(layers.layers),
        datasets=list(inputs.datasets),
        sources=list(inputs.sources),
        abroad=abroad,
        rivers=list(inputs.rivers),
    )


def map_place_ground(
    point: Point,
    district: str | None,
    measures: Measures,
    readings: tuple[Sequence[GroundReading], Sequence[DatasetRef]],
) -> MapPlaceGround:
    values, datasets = readings
    return MapPlaceGround(
        schema_version=GROUND_SCHEMA_VERSION,
        district=district,
        longitude=round(point[0], DEGREE_PLACES),
        latitude=round(point[1], DEGREE_PLACES),
        radius_km=DEPOSIT_RADIUS_KM,
        ground=ground_at(measures.layers, measures.at(point), values),
        classes=list(measures.layers.classes),
        layers=list(measures.layers.layers),
        datasets=list(datasets),
    )
