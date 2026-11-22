from __future__ import annotations

import re

__all__ = ["OPEN_LICENCE_NAMES", "OPEN_LICENCE_URL_PREFIXES", "RESTRICTING_PHRASES", "open_licence"]

OPEN_LICENCE_NAMES = frozenset(
    {
        "cc0",
        "cc zero",
        "cc by",
        "cc by sa",
        "pddl",
        "pd",
        "public domain",
        "public domain mark",
        "creative commons zero",
        "creative commons attribution",
        "creative commons attribution sharealike",
        "creative commons attribution share alike",
        "open data commons public domain dedication and license",
    }
)
OPEN_LICENCE_URL_PREFIXES = (
    "creativecommons.org/licenses/by/",
    "creativecommons.org/licenses/by-sa/",
    "creativecommons.org/publicdomain/zero/",
    "creativecommons.org/publicdomain/mark/",
    "opendatacommons.org/licenses/pddl/",
)
RESTRICTING_PHRASES = (
    "nc",
    "nd",
    "noncommercial",
    "non commercial",
    "noderivatives",
    "noderivs",
    "no derivatives",
    "no derivs",
    "all rights reserved",
)
PLACE_LIMITED_NAMES = frozenset({("public", "domain")})
PLACE_WORD = "in"
URL = re.compile(r"(?:https?://|www\.)\S+|(?:creativecommons|opendatacommons)\.org/\S+")
URL_START = re.compile(r"^(?:https?://)?(?:www\.)?")
URL_END = ".,;:)]}>'\""
WORD = re.compile(r"[a-z0-9]+(?:\.[0-9]+)*")
TRAILING_WORDS = frozenset(
    {"international", "unported", "generic", "universal", "igo", "license", "licence", "deed"}
)
VERSION = re.compile(r"^v?\d+(?:\.\d+)*$")
SHORTEST_PROSE_NAME = 3


def open_licence(licence: str | None) -> bool:
    text = (licence or "").strip().casefold()
    words = WORD.findall(text)
    if not words or _restricted(words):
        return False
    urls = [found.rstrip(URL_END) for found in URL.findall(text)]
    if urls:
        return all(_open_url(url) for url in urls)
    return _licence_name(words) in _OPEN_NAMES or _names_an_open_licence(words)


def _restricted(words: list[str]) -> bool:
    joined = f" {' '.join(words)} "
    return any(f" {phrase} " in joined for phrase in RESTRICTING_PHRASES)


def _open_url(text: str) -> bool:
    path = URL_START.sub("", text).split("?", 1)[0].split("#", 1)[0]
    path = path if path.endswith("/") else f"{path}/"
    return path.startswith(OPEN_LICENCE_URL_PREFIXES)


def _licence_name(words: list[str]) -> str:
    kept = list(words)
    while kept and (kept[-1] in TRAILING_WORDS or VERSION.match(kept[-1])):
        kept.pop()
    return " ".join(kept)


def _names_an_open_licence(words: list[str]) -> bool:
    return any(_occurs(name, words) for name in _PROSE_NAMES)


def _occurs(name: tuple[str, ...], words: list[str]) -> bool:
    limited = name in PLACE_LIMITED_NAMES
    for start in range(len(words) - len(name) + 1):
        end = start + len(name)
        if tuple(words[start:end]) != name:
            continue
        if not limited or end == len(words) or words[end] != PLACE_WORD:
            return True
    return False


_OPEN_NAMES = frozenset(_licence_name(WORD.findall(name)) for name in OPEN_LICENCE_NAMES)
_PROSE_NAMES = tuple(
    sorted(
        {tuple(name.split()) for name in _OPEN_NAMES if len(name) >= SHORTEST_PROSE_NAME},
        key=lambda name: (-len(name), name),
    )
)
