from __future__ import annotations

import re

__all__ = ["UNSTORABLE_CONTROLS", "storable_text"]

UNSTORABLE_CONTROLS = r"\x00-\x08\x0b\x0c\x0e-\x1f"
LINE_SEPARATING = re.compile(r"[\x0b\x0c\x1c-\x1f]")
DROPPED = re.compile(r"[\x00-\x08\x0e-\x1b]")
LINE_BREAK = "\n"


def storable_text(text: str) -> str:
    return DROPPED.sub("", LINE_SEPARATING.sub(LINE_BREAK, text))
