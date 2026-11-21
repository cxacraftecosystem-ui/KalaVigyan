from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

__all__ = ["MEASURED_FILES", "MEASURED_OUTPUT", "mirror_measured", "unmirrored"]

MEASURED_OUTPUT = Path("backend/app/data/layers")
MEASURED_FILES = ("relief.json", "rivers.json", "minerals.json")


def mirror_measured(drawn: Path, measured: Path, names: Iterable[str] = MEASURED_FILES) -> list[Path]:
    measured.mkdir(parents=True, exist_ok=True)
    written = []
    for name in names:
        target = measured / name
        target.write_bytes((drawn / name).read_bytes())
        written.append(target)
    return written


def unmirrored(drawn: Path, measured: Path, names: Iterable[str] = MEASURED_FILES) -> list[str]:
    return [
        name
        for name in names
        if not (measured / name).is_file() or (measured / name).read_bytes() != (drawn / name).read_bytes()
    ]
