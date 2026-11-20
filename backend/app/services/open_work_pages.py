from __future__ import annotations

import json
from collections.abc import Mapping
from functools import lru_cache
from types import MappingProxyType

from app.data.monograph_files import CONTENT_FILE, MONOGRAPHS_DIR

__all__ = ["CONTENT_FILE", "MONOGRAPHS_DIR", "monograph_layouts"]

LAYOUT_KEY = "layout"


@lru_cache(maxsize=1)
def monograph_layouts() -> Mapping[str, bool]:
    found = {}
    for folder in sorted(MONOGRAPHS_DIR.iterdir()):
        content = folder / CONTENT_FILE
        if folder.is_dir() and content.is_file():
            layout = json.loads(content.read_bytes().decode("utf-8")).get(LAYOUT_KEY)
            found[folder.name] = isinstance(layout, list) and bool(layout)
    return MappingProxyType(found)
