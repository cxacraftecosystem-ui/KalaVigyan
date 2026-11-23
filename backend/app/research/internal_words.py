from __future__ import annotations

import re

__all__ = ["INTERNAL_WORDS", "INTERNAL_WORDS_KIND", "internal_words"]

INTERNAL_WORDS_KIND = "INTERNAL_WORDS"
SAID_THINGS = r"(?:statements?|claims?|passages?|facts?|evidence|sources?|quotes?|knowledge|texts?|records?|findings?|data)"
INTERNAL_WORDS = re.compile(
    rf"\bstored\s+{SAID_THINGS}\b"
    r"|\buntrusted\b"
    r"|\bevidence\s+packs?\b"
    r"|\b(?:the|these|those)\s+(?:given|offered)\s+(?:statements?|claims?|passages?|sources?|quotes?|candidates?)\b"
    r"|\bcandidate\s+(?:statements?|claims?|passages?)\b",
    re.IGNORECASE,
)


def internal_words(text: str) -> str | None:
    found = INTERNAL_WORDS.search(text)
    return found.group(0) if found else None
