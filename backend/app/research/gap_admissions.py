from __future__ import annotations

import re
from collections.abc import Sequence

__all__ = ["GAP_ADMISSION", "SOURCE_GAP", "admits_gap", "gap_admissions", "without_source_gap"]

UNKNOWN_WORDS = r"(unknown|unclear|uncertain|undocumented|unrecorded|unidentified|unstudied)"
UNSAID_WORDS = r"(known|documented|recorded|available)"
UNSETTLED_WORDS = r"(known|documented|recorded|identified|established|determined|studied)"
SAYING_THINGS = r"(sources?|statements?|records?|texts?|passages?|stud(y|ies)|findings?)"
SAYING_WORDS = r"(say|state|mention|name|give|describe|record|explain|identify|specify|report)"
DETAIL_WORDS = r"(detail|details|detailed)"
LISTED_WORDS = r"([\w-]+,? ((or|and|nor) )?){0,5}"
SOURCE_GAPS = (
    r"no (cited |stored )?(source|evidence|information|data|statement|record|stud(y|ie))s?\b"
    rf"|no {LISTED_WORDS}{DETAIL_WORDS}\b"
    r"|not enough (cited )?evidence"
    r"|(could|can) ?not (find|be found)"
    rf"|{SAYING_THINGS} (do|does|did) not {SAYING_WORDS}\b"
)
SOURCE_GAP = re.compile(rf"\b({SOURCE_GAPS})", re.IGNORECASE)
GAP_ADMISSION = re.compile(
    rf"\b({SOURCE_GAPS}"
    rf"|not (yet )?{UNSAID_WORDS}\b"
    r"|(little|nothing) is known"
    rf"|(is|are|was|were|remains?|remained) (still |largely |as yet )?{UNKNOWN_WORDS}\b"
    rf"|(has|have|had) (not|never) (yet )?been {UNSETTLED_WORDS}\b"
    r"|we (do not|don['’]t) know)",
    re.IGNORECASE,
)


def admits_gap(text: str) -> bool:
    return GAP_ADMISSION.search(text) is not None


def gap_admissions(texts: Sequence[str]) -> list[str]:
    return [text for text in texts if admits_gap(text)]


def without_source_gap(text: str) -> str | None:
    if SOURCE_GAP.search(text) is None:
        return None
    return SOURCE_GAP.sub(" ", text)
