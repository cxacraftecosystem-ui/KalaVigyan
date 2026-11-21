from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

__all__ = [
    "ARROWS",
    "KEPT_FEATURES",
    "LATIN",
    "LATIN_EXT",
    "NEWSREADER_COMMIT",
    "NEWSREADER_FACES",
    "WEIGHT_RANGE",
    "Face",
    "Output",
    "codepoints",
    "css_range",
]

NEWSREADER_COMMIT = "5bd87dfc525c8a0d1d8529d3684716e00c3fc59a"
NEWSREADER_PATH = "ofl/newsreader"
WEIGHT_RANGE = (300, 600)

Span = tuple[int, int]

ARROWS: Span = (0x2190, 0x2199)

LATIN: tuple[Span, ...] = (
    (0x0000, 0x00FF),
    (0x0131, 0x0131),
    (0x0152, 0x0153),
    (0x02BB, 0x02BC),
    (0x02C6, 0x02C6),
    (0x02DA, 0x02DA),
    (0x02DC, 0x02DC),
    (0x0304, 0x0304),
    (0x0308, 0x0308),
    (0x0329, 0x0329),
    (0x2000, 0x206F),
    (0x20AC, 0x20AC),
    (0x2122, 0x2122),
    (0x2212, 0x2212),
    (0x2215, 0x2215),
    (0xFEFF, 0xFEFF),
    (0xFFFD, 0xFFFD),
)

LATIN_EXT: tuple[Span, ...] = (
    (0x0100, 0x02BA),
    (0x02BD, 0x02C5),
    (0x02C7, 0x02CC),
    (0x02CE, 0x02D7),
    (0x02DD, 0x02FF),
    (0x0300, 0x036F),
    (0x1D00, 0x1DBF),
    (0x1E00, 0x1EFF),
    (0x2070, 0x209F),
    (0x20A0, 0x20AB),
    (0x20AD, 0x20C0),
    (0x2100, 0x214F),
    (0x2150, 0x218F),
    (0x219A, 0x21FF),
    (0x2200, 0x2211),
    (0x2213, 0x2214),
    (0x2216, 0x22FF),
    (0x2C60, 0x2C7F),
    (0xA720, 0xA7FF),
    (0xFB00, 0xFB06),
)

KEPT_FEATURES = (
    "calt",
    "case",
    "ccmp",
    "clig",
    "curs",
    "kern",
    "liga",
    "lnum",
    "locl",
    "mark",
    "mkmk",
    "onum",
    "pnum",
    "rclt",
    "rlig",
    "rvrn",
    "tnum",
)


@dataclass(frozen=True)
class Face:
    source: str
    blob: str
    style: str


@dataclass(frozen=True)
class Output:
    face: Face
    name: str
    spans: tuple[Span, ...]


ROMAN = Face("Newsreader[opsz,wght].ttf", "ad4a9a8c44ec328c80b61c773f1ba02f6b5ed292", "normal")
ITALIC = Face("Newsreader-Italic[opsz,wght].ttf", "d25879656a601d44c49836f9e773d100190c62e1", "italic")

NEWSREADER_FACES = (
    Output(ROMAN, "newsreader-latin-var.woff2", LATIN),
    Output(ITALIC, "newsreader-italic-latin-var.woff2", LATIN),
    Output(ROMAN, "newsreader-latin-ext-var.woff2", LATIN_EXT),
    Output(ITALIC, "newsreader-italic-latin-ext-var.woff2", LATIN_EXT),
)


def css_range(spans: Iterable[Span]) -> str:
    return ", ".join(f"U+{start:04X}" if start == end else f"U+{start:04X}-{end:04X}" for start, end in spans)


def codepoints(spans: Iterable[Span]) -> frozenset[int]:
    return frozenset(point for start, end in spans for point in range(start, end + 1))
