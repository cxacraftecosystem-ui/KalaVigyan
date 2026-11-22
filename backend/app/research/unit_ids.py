from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

from app.core.errors import InvalidInput

__all__ = [
    "AUTHORED_UNITS",
    "DELIVERED_UNITS",
    "PLATE_UNITS",
    "UNIT_PREFIX",
    "UNIT_REF",
    "UNIT_REF_PATTERN",
    "UnitRange",
]

UNIT_PREFIX = "u"
UNIT_REF_PATTERN = r"^u\d{4}$"
UNIT_REF = re.compile(UNIT_REF_PATTERN)
NUMBER_DIGITS = 4


@dataclass(frozen=True)
class UnitRange:
    name: str
    first: int
    last: int

    def holds(self, unit: str) -> bool:
        return bool(UNIT_REF.match(unit)) and self.first <= int(unit[1:]) <= self.last

    def unit(self, offset: int) -> str:
        number = self.first + offset
        if offset < 0 or number > self.last:
            raise InvalidInput(f"The page holds no more room for {self.name} units")
        return f"{UNIT_PREFIX}{number:0{NUMBER_DIGITS}d}"

    def fresh(self, count: int, taken: Iterable[str]) -> list[str]:
        used = set(taken)
        found: list[str] = []
        offset = 0
        while len(found) < count:
            unit = self.unit(offset)
            if unit not in used:
                found.append(unit)
            offset += 1
        return found


AUTHORED_UNITS = UnitRange("authored", 1, 5000)
DELIVERED_UNITS = UnitRange("delivered", 5001, 8999)
PLATE_UNITS = UnitRange("picture", 9001, 9999)
