from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from atomic_write import write_text_atomically

__all__ = [
    "BASELINE_SCHEMA_VERSION",
    "BUDGET_COUNTS",
    "FALL_PASSES",
    "RATCHETED_COUNTS",
    "REGISTER_COUNT",
    "BaselineError",
    "RatchetStep",
    "compare",
    "read_baseline",
    "write_baseline",
]

BASELINE_SCHEMA_VERSION = 2
BUDGET_COUNTS = ("oversizedFiles", "longFunctions", "wideFunctions")
REGISTER_COUNT = "registerEntries"
RATCHETED_COUNTS = (*BUDGET_COUNTS, REGISTER_COUNT)
FALL_PASSES = frozenset({REGISTER_COUNT})


class BaselineError(ValueError):
    pass


@dataclass(frozen=True)
class RatchetStep:
    name: str
    baseline: int
    current: int

    @property
    def rose(self) -> bool:
        return self.current > self.baseline

    @property
    def fell(self) -> bool:
        return self.current < self.baseline

    @property
    def holds(self) -> bool:
        return not self.rose and (not self.fell or self.name in FALL_PASSES)


def read_baseline(path: Path) -> dict[str, int]:
    if not path.is_file():
        raise BaselineError(f"no hygiene baseline at {path}; create it with --update-baseline")
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or data.get("schemaVersion") != BASELINE_SCHEMA_VERSION:
        raise BaselineError(f"{path} is not a schemaVersion {BASELINE_SCHEMA_VERSION} hygiene baseline")
    counts = data.get("counts")
    if not isinstance(counts, dict) or set(counts) != set(RATCHETED_COUNTS):
        raise BaselineError(f"{path} must hold exactly these counts: {', '.join(RATCHETED_COUNTS)}")
    for name, value in counts.items():
        if not isinstance(value, int) or isinstance(value, bool) or value < 0:
            raise BaselineError(f"{path}: count {name} must be a non-negative integer, got {value!r}")
    return dict(counts)


def compare(baseline: Mapping[str, int], current: Mapping[str, int]) -> list[RatchetStep]:
    return [RatchetStep(name, baseline[name], current[name]) for name in RATCHETED_COUNTS]


def write_baseline(path: Path, counts: Mapping[str, int]) -> None:
    payload = {
        "schemaVersion": BASELINE_SCHEMA_VERSION,
        "counts": {name: counts[name] for name in RATCHETED_COUNTS},
    }
    write_text_atomically(path, json.dumps(payload, indent=2) + "\n")
