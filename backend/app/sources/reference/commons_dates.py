from __future__ import annotations

import re
from typing import Any

from ..records import clean_text, markup_text, partial_date_of

__all__ = ["original_date"]

MONTHS = (
    "january",
    "february",
    "march",
    "april",
    "may",
    "june",
    "july",
    "august",
    "september",
    "october",
    "november",
    "december",
)
FOOTNOTE = re.compile(r"\[[0-9]+\]")
UPLOAD_DATE = re.compile(r"\(original upload date\)$", re.IGNORECASE)
EXIF_NOTE = re.compile(r" ?\(according to exif data\)$", re.IGNORECASE)
TAKEN = re.compile(r"^taken (?:on|in) ", re.IGNORECASE)
TIME_OF_DAY = r"[ T][0-9]{2}:[0-9]{2}(?::[0-9]{2}(?:\.[0-9]+)?)?(?:Z|[+-][0-9]{2}:?[0-9]{2})?"
ISO_DATE = re.compile(r"[0-9]{4}(?:-[0-9]{2}){0,2}(?:" + TIME_OF_DAY + r")?")
YEAR = re.compile(r"(?:(?:circa|ca\.|c\.) ?)?([0-9]{4})", re.IGNORECASE)
NAMED_MONTH = re.compile(r"(?:([0-9]{1,2}) )?([a-z]+) ([0-9]{4})", re.IGNORECASE)
STATED = re.compile(r"date QS:P571,\+([0-9]{4})-([0-9]{2})-([0-9]{2})T00:00:00Z/(9|10|11)(?![0-9,])")
STATED_PARTS = {"9": 1, "10": 2, "11": 3}


def original_date(value: Any) -> str | None:
    shown = _shown(value)
    if shown is not None and UPLOAD_DATE.search(shown):
        return None
    return (_written_date(shown) if shown else None) or _stated_date(value)


def _shown(value: Any) -> str | None:
    text = markup_text(value)
    return clean_text(FOOTNOTE.sub("", text)) if text else None


def _written_date(shown: str) -> str | None:
    text = TAKEN.sub("", EXIF_NOTE.sub("", shown))
    if ISO_DATE.fullmatch(text):
        return partial_date_of(text)
    year = YEAR.fullmatch(text)
    if year is not None:
        return year.group(1)
    return _named_month_date(text)


def _named_month_date(text: str) -> str | None:
    match = NAMED_MONTH.fullmatch(text)
    if match is None or match.group(2).casefold() not in MONTHS:
        return None
    day, month, year = match.groups()
    parts = [year, f"{MONTHS.index(month.casefold()) + 1:02d}"]
    if day:
        parts.append(f"{int(day):02d}")
    return partial_date_of("-".join(parts))


def _stated_date(value: Any) -> str | None:
    match = STATED.search(value) if isinstance(value, str) else None
    if match is None:
        return None
    year, month, day, precision = match.groups()
    return partial_date_of("-".join((year, month, day)[: STATED_PARTS[precision]]))
