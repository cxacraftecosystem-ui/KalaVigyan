from __future__ import annotations

import re
from collections.abc import Sequence

__all__ = ["GAP_ADMISSION", "admits_gap", "gap_admissions"]

UNKNOWN_WORDS = r"(unknown|unclear|uncertain|undocumented|unrecorded|unidentified|unstudied)"
UNSAID_WORDS = r"(known|documented|recorded|available)"
UNSETTLED_WORDS = r"(known|documented|recorded|identified|established|determined|studied)"
GAP_ADMISSION = re.compile(
    r"\b(no (cited |stored )?(source|evidence|information|data)s?\b"
    r"|not enough (cited )?evidence"
    r"|(could|can) ?not (find|be found)"
    rf"|not (yet )?{UNSAID_WORDS}\b"
    r"|(little|nothing) is known"
    r"|sources? (do|does) not (say|state|mention)"
    rf"|(is|are|was|were|remains?|remained) (still |largely |as yet )?{UNKNOWN_WORDS}\b"
    rf"|(has|have|had) (not|never) (yet )?been {UNSETTLED_WORDS}\b"
    r"|we (do not|don['\u2019]t) know)",
    re.IGNORECASE,
)


def admits_gap(text: str) -> bool:
    return GAP_ADMISSION.search(text) is not None


def gap_admissions(texts: Sequence[str]) -> list[str]:
    return [text for text in texts if admits_gap(text)]
