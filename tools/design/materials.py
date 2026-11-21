from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from design.colour import from_oklch

__all__ = [
    "MATERIALS_FILE",
    "MATERIAL_PREFIX",
    "SCHEMA_VERSION",
    "Material",
    "load_materials",
    "material_names",
    "materials_from",
]

MATERIALS_FILE = Path(__file__).with_name("materials.json")
SCHEMA_VERSION = 1
MATERIAL_PREFIX = "dye-"
TOKEN = re.compile(r"^(dye-[a-z0-9]+(-[a-z0-9]+)*|dip-[1-9])$")
HEX = re.compile(r"^#[0-9A-F]{6}$")
CRAFT = re.compile(r"^[A-Za-z0-9]+(-[A-Za-z0-9]+)*$")
DOSSIER_ID = re.compile(r"^[A-Z]\d{2,3}$")
FIELDS = frozenset({"token", "craft", "material", "claims", "shows", "hex", "oklch", "stated"})


@dataclass(frozen=True)
class Material:
    token: str
    craft: str
    material: str
    claims: tuple[str, ...]
    shows: str
    hex: str
    stated: bool


def _colour(row: Mapping[str, Any]) -> str:
    given = [key for key in ("hex", "oklch") if key in row]
    if len(given) != 1:
        raise ValueError(f"{row.get('token')} gives its colour once, as hex or as oklch")
    if "hex" in row:
        if not HEX.fullmatch(row["hex"]):
            raise ValueError(f"{row['token']} hex {row['hex']!r} is #RRGGBB in capitals")
        return row["hex"]
    lightness, chroma, hue = row["oklch"]
    return from_oklch(lightness, chroma, hue)


def _material(row: Mapping[str, Any]) -> Material:
    unknown = set(row) - FIELDS
    if unknown:
        raise ValueError(f"{row.get('token')} has no field {sorted(unknown)}")
    if not TOKEN.fullmatch(row["token"]):
        raise ValueError(f"{row['token']!r} is not a depicted-material token (dye-<name> or dip-<n>)")
    if not CRAFT.fullmatch(row["craft"]) or not DOSSIER_ID.fullmatch(row["material"]):
        raise ValueError(f"{row['token']} names its craft by slug and its material by the dossier's id")
    claims = tuple(row["claims"])
    if not claims or not all(DOSSIER_ID.fullmatch(claim) for claim in claims):
        raise ValueError(f"{row['token']} names the facts that state its colour by their dossier ids")
    if not row["shows"].strip():
        raise ValueError(f"{row['token']} says what it shows")
    return Material(
        token=row["token"],
        craft=row["craft"],
        material=row["material"],
        claims=claims,
        shows=row["shows"],
        hex=_colour(row),
        stated=bool(row.get("stated", True)),
    )


def materials_from(body: Mapping[str, Any]) -> tuple[Material, ...]:
    if body.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError(f"The material records are schema version {SCHEMA_VERSION}")
    materials = tuple(_material(row) for row in body["materials"])
    tokens = [material.token for material in materials]
    if len(set(tokens)) != len(tokens):
        raise ValueError("Each depicted-material token is recorded once")
    return materials


def load_materials(path: Path = MATERIALS_FILE) -> tuple[Material, ...]:
    return materials_from(json.loads(path.read_text(encoding="utf-8")))


def material_names(materials: Sequence[Material]) -> tuple[str, ...]:
    return tuple(
        material.token.removeprefix(MATERIAL_PREFIX)
        for material in materials
        if material.token.startswith(MATERIAL_PREFIX)
    )
