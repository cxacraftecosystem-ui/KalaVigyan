from __future__ import annotations

import math
from collections.abc import Sequence
from itertools import pairwise

__all__ = [
    "PEAKS_HELD_BACK",
    "RANGES",
    "RIVERS",
    "label_angle",
    "line_label",
    "peak_text",
]

RIVERS: dict[str, tuple[str, int, float]] = {
    "Ganges": ("Ganga", 1, 0.62),
    "Brahmaputra": ("Brahmaputra", 1, 0.55),
    "Indus": ("Indus", 1, 0.5),
    "Godavari": ("Godavari", 1, 0.45),
    "Krishna": ("Krishna", 1, 0.45),
    "Narmada": ("Narmada", 1, 0.5),
    "Mahanadi": ("Mahanadi", 1, 0.5),
    "Kaveri": ("Kaveri", 1, 0.5),
    "Yamuna": ("Yamuna", 2, 0.5),
    "Tapti": ("Tapi", 2, 0.5),
    "Sutlej": ("Sutlej", 2, 0.5),
    "Chambal": ("Chambal", 2, 0.5),
    "Chenab": ("Chenab", 2, 0.5),
    "Son": ("Son", 2, 0.5),
    "Ghaghara": ("Ghaghara", 2, 0.5),
    "Tungabhadra": ("Tungabhadra", 3, 0.5),
    "Penner": ("Penner", 3, 0.5),
    "Mahi": ("Mahi", 3, 0.5),
    "Bhima": ("Bhima", 3, 0.5),
    "Wainganga": ("Wainganga", 3, 0.5),
    "Teesta": ("Teesta", 3, 0.5),
    "Jhelum": ("Jhelum", 3, 0.5),
    "Beas": ("Beas", 3, 0.5),
}

Placement = tuple[float, float, float]

RANGES: dict[str, tuple[str, int, Placement | None]] = {
    "Himalayas": ("Himalaya", 1, (78.35, 31.65, 32.0)),
    "Karakoram": ("Karakoram", 2, (78.25, 35.1, 0.0)),
    "Western Ghats": ("Western Ghats", 1, (74.55, 15.2, 72.0)),
    "Eastern Ghats": ("Eastern Ghats", 1, (81.3, 17.35, -46.0)),
    "Vindhya Range": ("Vindhya Range", 2, None),
    "Satpura Range": ("Satpura Range", 2, None),
    "Aravalli Range": ("Aravalli Range", 2, None),
    "Deccan Plateau": ("Deccan Plateau", 2, (77.6, 17.3, 0.0)),
    "Thar Desert": ("Thar Desert", 2, (71.6, 27.4, 0.0)),
    "Chota Nagpur Plateau": ("Chota Nagpur Plateau", 2, None),
    "Indo-Gangetic Plain": ("Indo-Gangetic Plain", 3, None),
}

PEAKS_HELD_BACK = frozenset({"Shahi Kangri"})

MAX_ANGLE = 75.0


def label_angle(dx: float, dy: float) -> float:
    if dx == 0 and dy == 0:
        return 0.0
    angle = math.degrees(math.atan2(dy, dx))
    if angle > 90:
        angle -= 180
    elif angle <= -90:
        angle += 180
    return round(max(-MAX_ANGLE, min(MAX_ANGLE, angle)), 1)


def _cumulative(points: Sequence[tuple[float, float]]) -> list[float]:
    lengths = [0.0]
    for (ax, ay), (bx, by) in pairwise(points):
        lengths.append(lengths[-1] + math.hypot(bx - ax, by - ay))
    return lengths


def _at(points: Sequence[tuple[float, float]], lengths: list[float], distance: float) -> tuple[float, float]:
    for index in range(1, len(points)):
        if lengths[index] >= distance:
            span = lengths[index] - lengths[index - 1] or 1.0
            share = (distance - lengths[index - 1]) / span
            (ax, ay), (bx, by) = points[index - 1], points[index]
            return ax + (bx - ax) * share, ay + (by - ay) * share
    return points[-1]


def line_label(
    points: Sequence[tuple[float, float]], share: float, reach: float
) -> tuple[float, float, float]:
    lengths = _cumulative(points)
    total = lengths[-1]
    middle = total * share
    x, y = _at(points, lengths, middle)
    ax, ay = _at(points, lengths, max(0.0, middle - reach))
    bx, by = _at(points, lengths, min(total, middle + reach))
    return x, y, label_angle(bx - ax, by - ay)


def peak_text(name: str, elevation: float) -> str:
    return f"{name} {round(elevation):,} m"
