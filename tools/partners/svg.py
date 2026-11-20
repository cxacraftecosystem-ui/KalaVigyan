from __future__ import annotations

import re
from collections.abc import Iterator
from itertools import pairwise

__all__ = ["Point", "compact_path", "minified_svg", "number_text", "subpaths"]

Point = tuple[float, float]

TOKEN = re.compile(r"[MmLlHhVvZz]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")
ROOT = re.compile(r"<svg\b[^>]*>")
SIZE = re.compile(r'\b(width|height)="([\d.]+)"')
GROUP = re.compile(r"<g\b([^>]*)>")
PATH = re.compile(r"<path\b[^>]*\bd=\"([^\"]+)\"[^>]*/>")
KEPT_ATTRIBUTES = re.compile(r'\b(fill|fill-rule)="([^"]+)"')


def number_text(value: float) -> str:
    text = f"{value:.3f}".rstrip("0").rstrip(".")
    if text in ("-0", ""):
        return "0"
    if text.startswith("0."):
        return text[1:]
    if text.startswith("-0."):
        return "-" + text[2:]
    return text


def _numbers(tokens: list[str], at: int) -> Iterator[float]:
    while at < len(tokens) and not tokens[at].isalpha():
        yield float(tokens[at])
        at += 1


def _step(command: str, values: list[float], here: Point) -> list[Point]:
    relative = command.islower()
    kind = command.upper()
    points: list[Point] = []
    x, y = here
    if kind in ("M", "L"):
        for at in range(0, len(values) - 1, 2):
            x, y = (x + values[at], y + values[at + 1]) if relative else (values[at], values[at + 1])
            points.append((x, y))
    elif kind == "H":
        for value in values:
            x = x + value if relative else value
            points.append((x, y))
    elif kind == "V":
        for value in values:
            y = y + value if relative else value
            points.append((x, y))
    return points


def subpaths(d: str) -> list[list[Point]]:
    tokens = TOKEN.findall(d)
    found: list[list[Point]] = []
    here: Point = (0.0, 0.0)
    at = 0
    while at < len(tokens):
        command = tokens[at]
        values = list(_numbers(tokens, at + 1))
        at += 1 + len(values)
        if command in "Zz":
            if found and found[-1]:
                here = found[-1][0]
            continue
        points = _step(command, values, here)
        if command in "Mm":
            found.append([])
        if not found:
            found.append([here])
        found[-1].extend(points)
        here = points[-1] if points else here
    return [path for path in found if len(path) >= 3]


def _rounded(path: list[Point], grid: float) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    for x, y in path:
        point = (round(x / grid), round(y / grid))
        if not out or out[-1] != point:
            out.append(point)
    if len(out) > 1 and out[0] == out[-1]:
        out.pop()
    return out


def _straightened(points: list[tuple[int, int]]) -> list[tuple[int, int]]:
    kept: list[tuple[int, int]] = []
    for point in points:
        if len(kept) >= 2:
            (ax, ay), (bx, by) = kept[-2], kept[-1]
            if (bx - ax) * (point[1] - ay) == (by - ay) * (point[0] - ax):
                kept[-1] = point
                continue
        kept.append(point)
    return kept


def _segment(dx: int, dy: int, grid: float) -> tuple[str, list[str]]:
    if dy == 0:
        return "h", [number_text(dx * grid)]
    if dx == 0:
        return "v", [number_text(dy * grid)]
    return "l", [number_text(dx * grid), number_text(dy * grid)]


def _joined(numbers: list[str], previous: str) -> str:
    out = ""
    for text in numbers:
        bare = not previous or previous.isalpha()
        glued = text.startswith("-") or (text.startswith(".") and "." in previous)
        out += text if bare or glued else " " + text
        previous = text
    return out


def _subpath_text(points: list[tuple[int, int]], start: str, grid: float) -> str:
    out = start
    command = ""
    previous = start[-1]
    for before, point in pairwise(points):
        kind, numbers = _segment(point[0] - before[0], point[1] - before[1], grid)
        if kind != command:
            out += kind
            previous, command = kind, kind
        out += _joined(numbers, previous)
        previous = numbers[-1]
    return out + "z"


def compact_path(d: str, grid: float) -> str:
    parts: list[str] = []
    last = (0, 0)
    for path in subpaths(d):
        points = _straightened(_rounded(path, grid))
        if len(points) < 3:
            continue
        sx, sy = points[0]
        if parts:
            start = "m" + _joined(
                [number_text((sx - last[0]) * grid), number_text((sy - last[1]) * grid)], "m"
            )
        else:
            start = "M" + _joined([number_text(sx * grid), number_text(sy * grid)], "M")
        parts.append(_subpath_text(points, start, grid))
        last = points[0]
    return "".join(parts)


def minified_svg(source: str, grid: float) -> str:
    root = ROOT.search(source)
    if root is None:
        raise ValueError("the file has no <svg> element")
    size = dict(SIZE.findall(root.group(0)))
    width, height = number_text(float(size["width"])), number_text(float(size["height"]))
    group = GROUP.search(source)
    attributes = "".join(
        f' {name}="{value}"' for name, value in KEPT_ATTRIBUTES.findall(group.group(1) if group else "")
    )
    paths = "".join(f'<path d="{compact_path(d, grid)}"/>' for d in PATH.findall(source))
    head = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" width="{width}" height="{height}">'
    return f"{head}<g{attributes}>{paths}</g></svg>\n"
