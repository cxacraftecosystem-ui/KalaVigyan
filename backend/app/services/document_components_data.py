from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from app.data.monograph_files import CONTENT_FILE

__all__ = ["KIND_DATA", "MOLECULE_DATA", "REGION_DATA", "borrowed_data", "merged_data", "monograph_data"]

MOLECULE_DATA = "mol-data"
REGION_DATA = "rs-data"
KIND_DATA: Mapping[str, str] = {
    "molecule_3d": MOLECULE_DATA,
    "map_layer": REGION_DATA,
    "map_sequence": REGION_DATA,
    "timeline_map": REGION_DATA,
}
MONOGRAPH_SLUG = re.compile(r"^[A-Za-z0-9-]+$")
MOLECULES_KEY = "molecules"
CID_KEY = "cid"


def monograph_data(root: Path, monograph: str) -> dict[str, Any]:
    if not MONOGRAPH_SLUG.fullmatch(monograph):
        return {}
    path = root / monograph / CONTENT_FILE
    if not path.is_file():
        return {}
    data = json.loads(path.read_bytes().decode("utf-8")).get("data")
    return data if isinstance(data, dict) else {}


def borrowed_data(data: Mapping[str, Any], kind: str, spec: Mapping[str, Any] | None) -> dict[str, Any]:
    key = KIND_DATA.get(kind)
    if key is None or key not in data:
        return {}
    block = data[key]
    if key != MOLECULE_DATA or not isinstance(block, Mapping) or spec is None:
        return {key: block}
    molecules = spec.get(MOLECULES_KEY, [])
    cids = {str(molecule.get(CID_KEY)) for molecule in molecules if isinstance(molecule, Mapping)}
    return {key: {cid: value for cid, value in block.items() if cid in cids}}


def merged_data(held: dict[str, Any], found: Mapping[str, Any]) -> None:
    for key, value in found.items():
        known = held.get(key)
        if key == MOLECULE_DATA and isinstance(known, dict) and isinstance(value, Mapping):
            held[key] = {**known, **value}
        else:
            held.setdefault(key, value)
