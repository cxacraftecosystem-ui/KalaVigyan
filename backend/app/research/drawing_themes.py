from __future__ import annotations

import re
from collections.abc import Mapping
from xml.etree import ElementTree

from .drawing_rules import local_name

__all__ = ["mixed_hex", "resolved_paint", "themed_svg"]

SVG_NS = "http://www.w3.org/2000/svg"
XLINK_NS = "http://www.w3.org/1999/xlink"
TOKEN = re.compile(r"var\(\s*--([a-z0-9-]+)\s*\)")
MIX = re.compile(
    r"color-mix\(\s*in srgb\s*,\s*var\(\s*--([a-z0-9-]+)\s*\)\s*(\d{1,3})%\s*,\s*var\(\s*--([a-z0-9-]+)\s*\)"
    r"(?:\s*\d{1,3}%)?\s*\)"
)
HEX = re.compile(r"^#([0-9A-Fa-f]{6})$")
FACE = "font-family"
INK = "ink-1"

ElementTree.register_namespace("", SVG_NS)
ElementTree.register_namespace("xlink", XLINK_NS)


def mixed_hex(first: str, share: int, second: str) -> str:
    a, b = _channels(first), _channels(second)
    weight = max(0, min(100, share)) / 100
    return "#" + "".join(f"{round(x * weight + y * (1 - weight)):02X}" for x, y in zip(a, b, strict=True))


def resolved_paint(text: str, palette: Mapping[str, str]) -> str:
    def mix(found: re.Match[str]) -> str:
        first, share, second = found.group(1), int(found.group(2)), found.group(3)
        if first not in palette or second not in palette:
            return found.group(0)
        return mixed_hex(palette[first], share, palette[second])

    def token(found: re.Match[str]) -> str:
        return palette.get(found.group(1), found.group(0))

    return TOKEN.sub(token, MIX.sub(mix, text))


def themed_svg(markup: str, palette: Mapping[str, str], face: str) -> str:
    root = ElementTree.fromstring(markup)
    for element in root.iter():
        for name, value in list(element.attrib.items()):
            element.set(name, resolved_paint(value, palette))
        if local_name(element.tag) == "style" and element.text:
            element.text = resolved_paint(element.text, palette)
    root.set(FACE, face)
    if INK in palette:
        root.set("color", palette[INK])
    return ElementTree.tostring(root, encoding="unicode")


def _channels(value: str) -> tuple[int, int, int]:
    found = HEX.match(value)
    if found is None:
        raise ValueError(f"{value!r} is not a six-digit hex colour")
    digits = found.group(1)
    return int(digits[0:2], 16), int(digits[2:4], 16), int(digits[4:6], 16)
