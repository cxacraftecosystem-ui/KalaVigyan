from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable

__all__ = ["SENTENCE_ENDS", "sentence_name", "upper_first"]

SENTENCE_ENDS = ".!?"
OPENERS = "\"'‘“([ "


def sentence_name(label: str, texts: Iterable[str]) -> str | None:
    written = label.strip()
    if not written:
        return None
    pattern = re.compile(rf"(?<![\w-]){re.escape(written)}(?![\w-])", re.IGNORECASE)
    found = Counter(
        match.group(0)
        for text in texts
        for match in pattern.finditer(text)
        if not _opens_a_sentence(text[: match.start()])
    )
    return found.most_common(1)[0][0] if found else None


def upper_first(text: str) -> str:
    return text[:1].upper() + text[1:]


def _opens_a_sentence(before: str) -> bool:
    kept = before.rstrip(OPENERS)
    return not kept or kept[-1] in SENTENCE_ENDS
