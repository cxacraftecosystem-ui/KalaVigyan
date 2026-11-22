from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

from .storable import storable_text

__all__ = [
    "QUOTE_MIN_CHARS",
    "QUOTE_OVERLAP_MIN",
    "content_stem",
    "content_stems",
    "content_words",
    "figures_in",
    "fold_digits",
    "formulas_in",
    "normalise_quote_lines",
    "normalise_quote_text",
    "numbers_in",
    "occurs_in_key",
    "quote_key",
    "quote_occurs",
    "quote_overlap",
    "spans_in_key",
    "trivial_quote",
    "unsupported_figures",
]

QUOTE_MIN_CHARS = 20
QUOTE_OVERLAP_MIN = 0.5
STEM_CHARS = 4

SOFT_HYPHEN = chr(0x00AD)
DASH_CODEPOINTS = (0x2010, 0x2011, 0x2012, 0x2013, 0x2014, 0x2212)
SINGLE_QUOTE_CODEPOINTS = (0x2018, 0x2019, 0x201A, 0x201B)
DOUBLE_QUOTE_CODEPOINTS = (0x201C, 0x201D, 0x201E, 0x201F)
TYPOGRAPHIC = str.maketrans(
    {chr(c): "-" for c in DASH_CODEPOINTS}
    | {chr(c): "'" for c in SINGLE_QUOTE_CODEPOINTS}
    | {chr(c): '"' for c in DOUBLE_QUOTE_CODEPOINTS}
)
ARABIC_DECIMAL_SEPARATOR = chr(0x066B)
ARABIC_THOUSANDS_SEPARATOR = chr(0x066C)
NUMERAL_SEPARATORS = str.maketrans({ARABIC_DECIMAL_SEPARATOR: ".", ARABIC_THOUSANDS_SEPARATOR: ","})
LINE_BREAK_HYPHEN = re.compile(r"(\w)-[ \t]*\r?\n\s*(\w)")
WHITESPACE = re.compile(r"\s+")
FORMULA = re.compile(r"(?<![A-Za-z0-9])(?:[A-Z][a-z]?\d*|\((?:[A-Z][a-z]?\d*)+\)\d*)+(?![A-Za-z0-9])")
NUMBER = re.compile(r"\d+(?:[.,]\d+)*")
WORD_HYPHEN = re.compile(r"(?<=[^\W\d_])-(?=[^\W\d_])")
CONTENT_WORD = re.compile(r"[^\W\d_]{4,}")
OPEN_BOUNDARY = r"(?<!\w)(?<!\d[.,])"
CLOSE_BOUNDARY = r"(?!\w)(?![.,]\d)"
STOP_WORDS = frozenset(
    {
        "about",
        "after",
        "also",
        "been",
        "before",
        "being",
        "both",
        "could",
        "does",
        "done",
        "each",
        "from",
        "have",
        "having",
        "into",
        "more",
        "most",
        "much",
        "must",
        "only",
        "onto",
        "other",
        "over",
        "same",
        "should",
        "some",
        "such",
        "than",
        "that",
        "their",
        "them",
        "then",
        "there",
        "these",
        "they",
        "this",
        "those",
        "through",
        "under",
        "very",
        "were",
        "what",
        "when",
        "where",
        "which",
        "while",
        "will",
        "with",
        "within",
        "would",
        "your",
    }
)


def normalise_quote_lines(text: str) -> list[str]:
    folded = unicodedata.normalize("NFKC", storable_text(text)).replace(SOFT_HYPHEN, "")
    joined = LINE_BREAK_HYPHEN.sub(r"\1\2", folded).translate(TYPOGRAPHIC)
    return [line for line in (WHITESPACE.sub(" ", raw).strip() for raw in joined.splitlines()) if line]


def normalise_quote_text(text: str) -> str:
    return " ".join(normalise_quote_lines(text))


def quote_key(text: str) -> str:
    return WORD_HYPHEN.sub("", normalise_quote_text(text))


def quote_occurs(quote: str, text: str) -> bool:
    return occurs_in_key(quote, quote_key(text))


def occurs_in_key(quote: str, key: str) -> bool:
    pattern = _needle_pattern(quote)
    return pattern is not None and pattern.search(key) is not None


def spans_in_key(quote: str, key: str) -> list[tuple[int, int]]:
    pattern = _needle_pattern(quote)
    return [] if pattern is None else [found.span() for found in pattern.finditer(key)]


def _needle_pattern(quote: str) -> re.Pattern[str] | None:
    needle = quote_key(quote)
    if not needle:
        return None
    opening = OPEN_BOUNDARY if needle[0].isalnum() else ""
    closing = CLOSE_BOUNDARY if needle[-1].isalnum() else ""
    return re.compile(opening + re.escape(needle) + closing)


def trivial_quote(quote: str) -> bool:
    return len(quote_key(quote)) < QUOTE_MIN_CHARS


def quote_overlap(text: str, quotes: Iterable[str]) -> float:
    wanted = content_stems(text)
    if not wanted:
        return 0.0
    found = {stem for quote in quotes for stem in content_stems(quote)}
    return len(wanted & found) / len(wanted)


def fold_digits(text: str) -> str:
    return "".join(_ascii_digit(ch) for ch in text.translate(NUMERAL_SEPARATORS))


def formulas_in(text: str) -> list[str]:
    folded = _figure_text(text)
    return list(
        dict.fromkeys(m.group() for m in FORMULA.finditer(folded) if any(c.isdigit() for c in m.group()))
    )


def numbers_in(text: str) -> list[str]:
    rest = FORMULA.sub(" ", _figure_text(text))
    return list(dict.fromkeys(m.group().replace(",", "") for m in NUMBER.finditer(rest)))


def figures_in(text: str) -> list[str]:
    return list(dict.fromkeys([*formulas_in(text), *numbers_in(text)]))


def unsupported_figures(text: str, cited_texts: Iterable[str]) -> list[str]:
    supported = {figure for cited in cited_texts for figure in figures_in(cited)}
    return [figure for figure in figures_in(text) if figure not in supported]


def content_words(text: str) -> list[str]:
    words = (word.casefold() for word in CONTENT_WORD.findall(quote_key(text)))
    return [word for word in words if word not in STOP_WORDS]


def content_stems(text: str) -> set[str]:
    return {content_stem(word) for word in content_words(text)}


def content_stem(word: str) -> str:
    return word.casefold()[:STEM_CHARS]


def _figure_text(text: str) -> str:
    return fold_digits(normalise_quote_text(text))


def _ascii_digit(char: str) -> str:
    value = unicodedata.decimal(char, None)
    return char if value is None else str(value)
