from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from design.colour import channels, delta_e, fmt_oklch, from_oklch, hex_to_rgb, rgb_to_hex
from design.materials import MATERIALS_FILE, Material, load_materials

__all__ = ["SYSTEM_FILE", "System", "colour_entry", "load_system", "mix", "specimen_hex"]

SYSTEM_FILE = Path(__file__).with_name("system.json")


@dataclass(frozen=True)
class System:
    data: dict[str, Any]
    materials: tuple[Material, ...] = field(default=())

    @property
    def themes(self) -> list[str]:
        return self.data["themes"]

    def theme_index(self, theme: str) -> int:
        return self.themes.index(theme)

    def sem(self, name: str, theme: str) -> str:
        for row in self.data["semantic"]:
            if row[0] == name:
                return row[4 + self.theme_index(theme)]
        raise KeyError(name)

    def resolve(self, value: str, theme: str) -> str:
        if "|" in value:
            return value.split("|")[self.theme_index(theme)]
        if value.startswith("#"):
            return value
        return self.sem(value, theme)

    def map_colour(self, name: str, theme: str) -> str:
        for row in self.data["map"]:
            if row[0] == name:
                return self.resolve(row[3 + self.theme_index(theme)], theme)
        raise KeyError(name)

    def reserved_min(self, colour: str, theme: str) -> tuple[float, str]:
        return min((round(delta_e(colour, self.sem(name, theme)), 1), name) for name in self.data["reserved"])


def load_system(path: Path = SYSTEM_FILE, materials: Path = MATERIALS_FILE) -> System:
    return System(json.loads(path.read_text(encoding="utf-8")), load_materials(materials))


def mix(foreground: str, background: str, alpha: float) -> str:
    front, back = hex_to_rgb(foreground), hex_to_rgb(background)
    return rgb_to_hex(*(back[i] * (1 - alpha) + front[i] * alpha for i in range(3)))


def colour_entry(colour: str) -> dict[str, str]:
    return {"hex": colour, "oklch": fmt_oklch(colour), "channels": channels(colour)}


def specimen_hex(row: list[Any]) -> str:
    return row[1] if row[1] else from_oklch(*row[3])
