from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from types import MappingProxyType
from typing import Any

from app.data.dataset_registry import registry_rows
from app.data.map_layers import LAYERS_DIR, MINERALS_FILE, RELIEF_FILE, RIVERS_FILE
from app.data.water_tiles import held_waters_index
from app.geo.datasets import registry_row_ref
from app.geo.layers import MAP_LAYERS
from app.research.datasets import DatasetRef

__all__ = [
    "PHYSICAL_FILES",
    "SiteLayer",
    "layer_row_refs",
    "physical_records",
    "site_layers",
]

PHYSICAL_FILES = MappingProxyType({"relief": RELIEF_FILE, "rivers": RIVERS_FILE, "minerals": MINERALS_FILE})
PHYSICAL_SHOWN = MappingProxyType(
    {
        "relief": (
            "Physical relief and mountains",
            "elevation bands with their hillshade, range names and spot heights",
        ),
        "rivers": (
            "Rivers and lakes",
            "rivers by rank, lakes and reservoirs, named from the file's own labels",
        ),
        "minerals": ("Mineral deposits", "mineral deposits as point symbols, one shape for each class"),
    }
)
WATERS = "waters"
WATERS_TITLE = "Small rivers, streams and dams"
WATERS_DRAWS = (
    "small rivers, streams and dams in a frame of at most 35 per cent of India's width, and the rivers and dams "
    "a places map's emphasis names"
)
DISTRICT_DRAWS = "each district filled by its value's class"
READ_ON = "readOn"
RETRIEVED_AT = "retrievedAt"


@dataclass(frozen=True)
class SiteLayer:
    name: str
    title: str
    draws: str
    records: tuple[DatasetRef, ...]
    named: bool = True


def layer_row_refs(body: Mapping[str, Any]) -> tuple[DatasetRef, ...]:
    source = body.get("source")
    rows = body.get("datasets") or ([source] if isinstance(source, Mapping) else [])
    refs: dict[str, DatasetRef] = {}
    for row in rows:
        if isinstance(row, Mapping) and row.get("code"):
            refs.setdefault(str(row["code"]), registry_row_ref({**row, RETRIEVED_AT: row.get(READ_ON)}))
    return tuple(refs.values())


@cache
def physical_records(name: str) -> tuple[DatasetRef, ...]:
    return layer_row_refs(json.loads((LAYERS_DIR / PHYSICAL_FILES[name]).read_text(encoding="utf-8")))


def site_layers() -> tuple[SiteLayer, ...]:
    registry = {str(row["code"]): row for row in registry_rows()}
    physical = [SiteLayer(name, *PHYSICAL_SHOWN[name], physical_records(name)) for name in PHYSICAL_FILES]
    waters = SiteLayer(WATERS, WATERS_TITLE, WATERS_DRAWS, layer_row_refs(held_waters_index()), named=False)
    district = [
        SiteLayer(
            spec.id,
            spec.title,
            DISTRICT_DRAWS,
            (registry_row_ref(registry[spec.dataset_code]),) if spec.dataset_code in registry else (),
        )
        for spec in MAP_LAYERS
    ]
    return (*physical, waters, *district)
