from __future__ import annotations

import re

__all__ = ["ORGANISATION_WORDS", "split_authors"]

ORGANISATION_WORDS = re.compile(
    r"\b(?:academy|administration|association|board|centre|center|commission|committee|company|co-operative"
    r"|corporation|council|department|foundation|government|institute|ministry|museum|office|registry"
    r"|samiti|sangathan|society|trust|university)\b",
    re.IGNORECASE,
)
LIST_SEPARATOR = re.compile(r";")
NAME_SEPARATOR = re.compile(r"\band\b")
BRACKETED = "_"


def split_authors(author: str | None) -> list[str]:
    if not author:
        return []
    names: list[str] = []
    for part in _split_outside_brackets(author, LIST_SEPARATOR):
        if ORGANISATION_WORDS.search(_masked(part)):
            names.append(part)
        else:
            names.extend(_split_outside_brackets(part, NAME_SEPARATOR))
    return names


def _split_outside_brackets(text: str, separator: re.Pattern[str]) -> list[str]:
    masked = _masked(text)
    parts: list[str] = []
    start = 0
    for found in separator.finditer(masked):
        parts.append(text[start : found.start()])
        start = found.end()
    parts.append(text[start:])
    return [" ".join(part.split()) for part in parts if part.strip()]


def _masked(text: str) -> str:
    depth = 0
    shown: list[str] = []
    for character in text:
        if character == "(":
            depth += 1
        shown.append(BRACKETED if depth and character not in "()" else character)
        if character == ")":
            depth = max(0, depth - 1)
    return "".join(shown)
