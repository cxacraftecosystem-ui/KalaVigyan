from __future__ import annotations

from collections.abc import Mapping
from typing import Any

__all__ = ["spec_strings"]


def spec_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        return [found for item in value.values() for found in spec_strings(item)]
    if isinstance(value, list | tuple):
        return [found for item in value for found in spec_strings(item)]
    return []
