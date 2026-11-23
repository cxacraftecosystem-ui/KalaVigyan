from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass

__all__ = [
    "FRONT_LINES_READ",
    "PERIODICAL_WORDS",
    "PRODUCER_NAMES",
    "SOFTWARE_NAMES",
    "FrontPage",
    "front_page",
    "producer_token",
]

FRONT_LINES_READ = 15
TITLE_LINES_MAX = 6
TITLE_MAX_CHARS = 300
JOURNAL_MAX_CHARS = 200
AUTHOR_LINE_MAX_CHARS = 300
AUTHORS_MAX = 12
NAME_TOKENS = (2, 5)
MONTH_LETTERS_MIN = 3
PRODUCER_NAMES = frozenset(
    {
        "sys",
        "user",
        "admin",
        "administrator",
        "owner",
        "author",
        "unknown",
        "default",
        "test",
        "guest",
        "root",
    }
)
SOFTWARE_NAMES = (
    "gpl ghostscript",
    "ghostscript",
    "microsoft",
    "adobe",
    "acrobat",
    "pscript",
    "pdftex",
    "latex",
    "tex",
    "openoffice",
    "libreoffice",
    "word",
)
PERIODICAL_WORDS = frozenset(
    {
        "journal",
        "bulletin",
        "proceedings",
        "transactions",
        "annals",
        "review",
        "letters",
        "quarterly",
        "magazine",
    }
)
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
NAME_PARTICLES = frozenset({"de", "da", "del", "der", "di", "du", "la", "le", "van", "von", "bin", "al"})
NOT_NAMES = frozenset(
    {"and", "of", "the", "in", "for", "to", "with", "on", "at", "by", "from", "a", "an", "or"}
)
GLYPH_NAME = re.compile(r"(?<!\S)/[A-Za-z][\w.]*")
ISSUE = re.compile(
    r"^(?P<journal>.+?)[\s,;:|\-–—]+(?P<month>[A-Za-z]{3,9})\.?,?\s+(?P<year>(?:1[89]|20)\d{2})\b"
)
JOURNAL_END = re.compile(r",|\s(?:vol|no|issue)\b\.?", re.IGNORECASE)
FOOTNOTE_MARKS = re.compile(r"[*†‡§¶#^]|\d+")
AUTHOR_SEPARATORS = re.compile(r",|;|\s+and\s+|\s*&\s*")
INITIALS = re.compile(r"^(?:[A-Z]\.-?)+$")
NAME_WORD = re.compile(r"^[^\W\d_][^\W\d_'’\-]*$")


@dataclass(frozen=True)
class FrontPage:
    journal: str | None = None
    published: str | None = None
    authors: tuple[str, ...] = ()
    title: str | None = None


def producer_token(author: str) -> bool:
    text = " ".join(author.split())
    folded = text.casefold()
    if not any(character.isalpha() for character in folded) or folded in PRODUCER_NAMES:
        return True
    if any(_starts_with_word(folded, name) for name in SOFTWARE_NAMES):
        return True
    return " " not in text and not any(character.isupper() for character in text)


def front_page(text: str) -> FrontPage:
    lines = [_unglyphed(line) for line in text.splitlines()[:FRONT_LINES_READ]]
    lines = [line for line in lines if line]
    found = next(((at, issue) for at, line in enumerate(lines) if (issue := _issue(line)) is not None), None)
    start = found[0] + 1 if found is not None else 0
    journal, published = found[1] if found is not None else (None, None)
    for at in range(start + 1, min(start + 1 + TITLE_LINES_MAX, len(lines))):
        authors = _authors(lines[at])
        if authors:
            return FrontPage(journal, published, authors, _title(lines[start:at]))
    after_journal = lines[start] if found is not None and start < len(lines) else None
    return FrontPage(journal, published, title=_title([after_journal]) if after_journal else None)


def _starts_with_word(folded: str, name: str) -> bool:
    if not folded.startswith(name):
        return False
    return len(folded) == len(name) or not folded[len(name)].isalpha()


def _unglyphed(line: str) -> str:
    return " ".join(GLYPH_NAME.sub(" ", line).split())


def _issue(line: str) -> tuple[str, str] | None:
    match = ISSUE.match(line)
    month = _month(match.group("month")) if match is not None else None
    if match is None or month is None:
        return None
    journal = JOURNAL_END.split(match.group("journal"))[0].strip(" .,;:|-–—")
    words = {word.casefold() for word in re.findall(r"[^\W\d_]+", journal)}
    if not journal[:1].isupper() or not words & PERIODICAL_WORDS or len(journal) > JOURNAL_MAX_CHARS:
        return None
    return journal, f"{match.group('year')}-{month:02d}"


def _month(word: str) -> int | None:
    folded = word.casefold()
    if len(folded) < MONTH_LETTERS_MIN:
        return None
    return next((at + 1 for at, name in enumerate(MONTHS) if name.startswith(folded)), None)


def _authors(line: str) -> tuple[str, ...]:
    if len(line) > AUTHOR_LINE_MAX_CHARS:
        return ()
    parts = [" ".join(part.split()) for part in AUTHOR_SEPARATORS.split(FOOTNOTE_MARKS.sub(" ", line))]
    names = [part for part in parts if part]
    if not names or len(names) > AUTHORS_MAX or not all(_person(name.split()) for name in names):
        return ()
    return tuple(names)


def _person(tokens: Sequence[str]) -> bool:
    least, most = NAME_TOKENS
    if not least <= len(tokens) <= most:
        return False
    if any(token.casefold() in NOT_NAMES for token in tokens):
        return False
    words = [token for token in tokens if not INITIALS.match(token)]
    return bool(words) and all(_name_word(token) for token in words)


def _name_word(token: str) -> bool:
    if token in NAME_PARTICLES:
        return True
    return bool(NAME_WORD.match(token)) and token[0].isupper() and len(token) > 1


def _title(lines: Sequence[str]) -> str | None:
    title = " ".join(lines).strip()
    return title if 0 < len(title) <= TITLE_MAX_CHARS else None
