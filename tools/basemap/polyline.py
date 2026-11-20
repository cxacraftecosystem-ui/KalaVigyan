from __future__ import annotations

import re
from collections.abc import Iterable, Sequence

__all__ = ["SCALE", "decode_records", "encode_records", "encode_ring", "india_payload"]

ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
VALUES = {character: index for index, character in enumerate(ALPHABET)}
SCALE = 1000
CHUNK = 0x20

Point = tuple[float, float]


def _encode_int(value: int) -> str:
    folded = ~(value << 1) if value < 0 else value << 1
    out = []
    while folded >= CHUNK:
        out.append(ALPHABET[(folded & 0x1F) | CHUNK])
        folded >>= 5
    out.append(ALPHABET[folded])
    return "".join(out)


def _scaled(points: Iterable[Point]) -> list[tuple[int, int]]:
    scaled: list[tuple[int, int]] = []
    for longitude, latitude in points:
        point = (round(longitude * SCALE), round(latitude * SCALE))
        if not scaled or scaled[-1] != point:
            scaled.append(point)
    return scaled


def encode_records(records: Sequence[Sequence[Point]], holes: Sequence[bool] | None = None) -> str:
    parts: list[str] = []
    x = y = 0
    for index, record in enumerate(records):
        points = _scaled(record)
        parts.append(_encode_int(len(points)))
        if holes is not None:
            parts.append(_encode_int(1 if holes[index] else 0))
        for px, py in points:
            parts.append(_encode_int(px - x) + _encode_int(py - y))
            x, y = px, py
    return "".join(parts)


def encode_ring(ring: Sequence[Point]) -> str:
    open_ring = list(ring[:-1]) if len(ring) > 1 and tuple(ring[0]) == tuple(ring[-1]) else list(ring)
    return encode_records([open_ring])


def _read_ints(payload: str) -> Iterable[int]:
    index = 0
    while index < len(payload):
        shift = result = 0
        while True:
            value = VALUES[payload[index]]
            index += 1
            result |= (value & 0x1F) << shift
            shift += 5
            if value < CHUNK:
                break
        yield ~(result >> 1) if result & 1 else result >> 1


def decode_records(payload: str, hole_flag: bool) -> list[tuple[bool, list[Point]]]:
    numbers = iter(_read_ints(payload))
    records: list[tuple[bool, list[Point]]] = []
    x = y = 0
    for count in numbers:
        if count <= 0:
            break
        hole = next(numbers) != 0 if hole_flag else False
        points: list[Point] = []
        for _ in range(count):
            x += next(numbers)
            y += next(numbers)
            points.append((x / SCALE, y / SCALE))
        records.append((hole, points))
    return records


def india_payload(source: str) -> str:
    match = re.search(r"const PAYLOAD =\s*((?:\"[^\"]*\"\s*\+?\s*)+);", source)
    if not match:
        raise ValueError("the India outline payload was not found")
    return "".join(re.findall(r"\"([^\"]*)\"", match.group(1)))
