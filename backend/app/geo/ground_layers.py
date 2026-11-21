from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.research.place_ground import GroundLayer, MineralClass

__all__ = [
    "Band",
    "Deposit",
    "GroundLayers",
    "Line",
    "RiverLabel",
    "decode_records",
    "ground_layers",
    "line_of",
]

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
VALUES = {character: index for index, character in enumerate(ALPHABET)}
SCALE = 1000
CHUNK = 0x20
LOW_BITS = 0x1F
SHIFT = 5
RING_POINTS = 3
LINE_POINTS = 2
DIGEST_CHARS = 12
COMMODITY_SEPARATOR = ","
NATURAL_EARTH = "Natural Earth"
NATURAL_EARTH_SCALE = "1:10m"

Point = tuple[float, float]
Box = tuple[float, float, float, float]


@dataclass(frozen=True)
class Line:
    points: tuple[Point, ...]
    box: Box
    rank: int = 0


@dataclass(frozen=True)
class Band:
    low_m: int
    rings: tuple[Line, ...]


@dataclass(frozen=True)
class Deposit:
    dep_id: int
    name: str
    longitude: float
    latitude: float
    class_index: int
    status: str
    commodities: tuple[str, ...]


@dataclass(frozen=True)
class RiverLabel:
    text: str
    longitude: float
    latitude: float
    angle: float


@dataclass(frozen=True)
class GroundLayers:
    breaks: tuple[int, ...]
    bands: tuple[Band, ...]
    rivers: tuple[Line, ...]
    lakes: tuple[Line, ...]
    labels: tuple[RiverLabel, ...]
    deposits: tuple[Deposit, ...]
    classes: tuple[MineralClass, ...]
    layers: tuple[GroundLayer, ...]


def _numbers(payload: str) -> Iterator[int]:
    index = 0
    while index < len(payload):
        shift = result = 0
        while True:
            value = VALUES[payload[index]]
            index += 1
            result |= (value & LOW_BITS) << shift
            shift += SHIFT
            if value < CHUNK:
                break
        yield ~(result >> 1) if result & 1 else result >> 1


def decode_records(payload: str) -> list[list[Point]]:
    numbers = _numbers(payload)
    records: list[list[Point]] = []
    x = y = 0
    for count in numbers:
        if count <= 0:
            break
        points: list[Point] = []
        for _ in range(count):
            x += next(numbers)
            y += next(numbers)
            points.append((x / SCALE, y / SCALE))
        records.append(points)
    return records


def line_of(points: Sequence[Point], rank: int = 0) -> Line:
    longitudes = [point[0] for point in points]
    latitudes = [point[1] for point in points]
    box = (min(longitudes), min(latitudes), max(longitudes), max(latitudes))
    return Line(points=tuple(points), box=box, rank=rank)


def _rings(encoded: Sequence[str]) -> tuple[Line, ...]:
    return tuple(
        line_of(ring) for text in encoded for ring in decode_records(text) if len(ring) >= RING_POINTS
    )


def _rivers(ranks: Sequence[Mapping[str, Any]]) -> tuple[Line, ...]:
    return tuple(
        line_of(record, int(group["rank"]))
        for group in ranks
        for record in decode_records(group["lines"])
        if len(record) >= LINE_POINTS
    )


def _deposit(row: Sequence[Any], statuses: Sequence[str]) -> Deposit:
    dep_id, name, _state, longitude, latitude, class_index, status, commodities = row
    named = tuple(part.strip() for part in str(commodities).split(COMMODITY_SEPARATOR) if part.strip())
    return Deposit(
        dep_id=int(dep_id),
        name=str(name),
        longitude=float(longitude),
        latitude=float(latitude),
        class_index=int(class_index),
        status=statuses[int(status)],
        commodities=named,
    )


def _edition(row: Mapping[str, Any]) -> str:
    version = row.get("version")
    return str(version) if version else f"sha256 {str(row['sha256'])[:DIGEST_CHARS]}"


def _natural_earth(key: str, row: Mapping[str, Any], licence: str) -> GroundLayer:
    return GroundLayer(
        key=key,
        title=f"{NATURAL_EARTH} {NATURAL_EARTH_SCALE} {row['dataset']}",
        publisher=NATURAL_EARTH,
        edition=_edition(row),
        url=str(row["url"]),
        licence=licence,
        citation=None,
    )


def _published(key: str, row: Mapping[str, Any]) -> GroundLayer:
    return GroundLayer(
        key=key,
        title=str(row["dataset"]),
        publisher=str(row["publisher"]),
        edition=_edition(row),
        url=str(row["url"]),
        licence=str(row["licence"]),
        citation=row.get("citation"),
    )


def _layers(
    relief: Mapping[str, Any], rivers: Mapping[str, Any], minerals: Mapping[str, Any]
) -> tuple[GroundLayer, ...]:
    lines, lakes = rivers["datasets"][0], rivers["datasets"][1]
    return (
        _published("ETOPO1", relief["datasets"][0]),
        _natural_earth("NE_RIVERS", lines, str(rivers["licence"])),
        _natural_earth("NE_LAKES", lakes, str(rivers["licence"])),
        _published("USGS_MRDS", minerals["source"]),
    )


def ground_layers(
    relief: Mapping[str, Any], rivers: Mapping[str, Any], minerals: Mapping[str, Any]
) -> GroundLayers:
    statuses = list(minerals["statuses"])
    return GroundLayers(
        breaks=tuple(int(value) for value in relief["breaks"]),
        bands=tuple(Band(int(band["min"]), _rings(band["rings"])) for band in relief["bands"]),
        rivers=_rivers(rivers["ranks"]),
        lakes=_rings(rivers["lakes"]),
        labels=tuple(
            RiverLabel(
                str(label["text"]), float(label["longitude"]), float(label["latitude"]), float(label["angle"])
            )
            for label in rivers["labels"]
        ),
        deposits=tuple(_deposit(row, statuses) for row in minerals["sites"]),
        classes=tuple(MineralClass(id=str(c["id"]), label=str(c["label"])) for c in minerals["classes"]),
        layers=_layers(relief, rivers, minerals),
    )
