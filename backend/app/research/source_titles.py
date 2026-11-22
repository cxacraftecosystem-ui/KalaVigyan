from __future__ import annotations

import re

__all__ = ["HEADING_MAX_CHARS", "TITLE_WORDS_MIN", "first_heading", "junk_title", "usable_title"]

TITLE_WORDS_MIN = 3
HEADING_MAX_CHARS = 300
HEADING_LINES_READ = 40
FILE_NAME = re.compile(r"^[\w\-.]+\.[A-Za-z0-9]{2,5}$")
LETTER_WORD = re.compile(r"[^\W\d_]{2,}")


def junk_title(title: str | None) -> bool:
    text = (title or "").strip()
    if not text or FILE_NAME.fullmatch(text):
        return True
    return len(LETTER_WORD.findall(text)) < TITLE_WORDS_MIN


def usable_title(*offered: str | None) -> str | None:
    return next((title.strip() for title in offered if title is not None and not junk_title(title)), None)


def first_heading(text: str | None) -> str | None:
    lines = (line.strip() for line in (text or "").splitlines()[:HEADING_LINES_READ])
    return next((line for line in lines if len(line) <= HEADING_MAX_CHARS and not junk_title(line)), None)
