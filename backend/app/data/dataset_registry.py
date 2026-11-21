from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

__all__ = ["REGISTRY_PATH", "SCHEMA_VERSION", "registry_rows"]

REGISTRY_PATH = Path(__file__).resolve().parent / "datasets" / "registry.json"
SCHEMA_VERSION = 1


@cache
def registry_rows() -> tuple[dict[str, Any], ...]:
    body = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    if body.get("schemaVersion") != SCHEMA_VERSION:
        raise ValueError(f"The dataset registry is schema version {SCHEMA_VERSION}")
    return tuple(body["datasets"])
