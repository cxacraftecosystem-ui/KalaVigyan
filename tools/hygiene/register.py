from __future__ import annotations

from collections.abc import Mapping
from pathlib import PurePosixPath

__all__ = [
    "ENTRY_MARK",
    "REGISTER_FILE",
    "REGISTER_RISE",
    "RegisterError",
    "count_entries",
    "register_entries",
]

REGISTER_FILE = PurePosixPath("docs/TECH_DEBT.md")
ENTRY_MARK = "### "
FENCE_MARK = "```"
REGISTER_RISE = (
    f"{REGISTER_FILE} gained entries; its count may only fall, so clear as many in the same change"
)


class RegisterError(ValueError):
    pass


def count_entries(text: str) -> int:
    count = 0
    fenced = False
    for line in text.splitlines():
        if line.startswith(FENCE_MARK):
            fenced = not fenced
        elif not fenced and line.startswith(ENTRY_MARK):
            count += 1
    return count


def register_entries(contents: Mapping[PurePosixPath, bytes]) -> int:
    raw = contents.get(REGISTER_FILE)
    if raw is None:
        raise RegisterError(f"no debt register at {REGISTER_FILE}; its entry count is ratcheted")
    return count_entries(raw.decode("utf-8", errors="replace"))
