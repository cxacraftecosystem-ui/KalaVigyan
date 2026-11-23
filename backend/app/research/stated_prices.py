from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal

from .blocks_insight import CURRENCY_MARKS, SCALE_WORDS
from .stated_quantities import NUMBER_PATTERN, stated_decimal

__all__ = ["StatedPrice", "stated_prices"]

RANGE_JOIN = r"\s*(?:-|–|—|to)\s*"
SCALE = r"(?:\s+(?P<scale>(?i:thousand|lakhs?|crores?)))?"
PREFIXED = re.compile(
    rf"(?P<mark>₹|US\$|\$|(?<![^\W\d_])(?i:rs\.?|inr|usd)(?![^\W\d_]))\s*(?P<low>{NUMBER_PATTERN})"
    rf"(?:{RANGE_JOIN}(?:(?:₹|(?i:rs\.?))\s*)?(?P<high>{NUMBER_PATTERN}))?{SCALE}(?![\w])"
)
SUFFIXED = re.compile(
    rf"(?<![\w.,])(?P<low>{NUMBER_PATTERN})(?:{RANGE_JOIN}(?P<high>{NUMBER_PATTERN}))?{SCALE}"
    r"\s+(?P<mark>(?i:rupees?|dollars?))(?![\w])"
)
PER = re.compile(
    r"\s*(?:(?i:per|an?)\s+|/\s*)(?P<per>[^\W\d_]+)(?![^\W\d_])(?!\s+(?i:ago|back|before|earlier|later)(?!\w))"
)
NOT_PER = frozenset(
    {
        "bit",
        "couple",
        "few",
        "further",
        "little",
        "lot",
        "maximum",
        "mere",
        "minimum",
        "number",
        "total",
        "while",
    }
)


@dataclass(frozen=True)
class StatedPrice:
    stated: str
    low: Decimal
    high: Decimal | None
    currency: str
    scale: str | None
    per: str | None


def stated_prices(text: str) -> list[StatedPrice]:
    found: dict[str, StatedPrice] = {}
    for pattern in (PREFIXED, SUFFIXED):
        for match in pattern.finditer(text):
            price = _price(match, text)
            if price is not None:
                found.setdefault(price.stated.casefold(), price)
    return list(found.values())


def _price(match: re.Match[str], text: str) -> StatedPrice | None:
    low, high = stated_decimal(match.group("low")), stated_decimal(match.group("high"))
    currency = _currency(match.group("mark"))
    if low is None or currency is None or (match.group("high") and (high is None or high <= low)):
        return None
    return StatedPrice(
        stated=match.group(0),
        low=low,
        high=high,
        currency=currency,
        scale=_scale(match.group("scale")),
        per=_per(text, match.end()),
    )


def _per(text: str, end: int) -> str | None:
    found = PER.match(text, end)
    if found is None or found.group("per").casefold() in NOT_PER:
        return None
    return found.group("per")


def _currency(mark: str) -> str | None:
    folded = mark.casefold().rstrip(".")
    folded = "$" if folded == "us$" else folded
    return next((code for code, marks in CURRENCY_MARKS.items() if folded in marks), None)


def _scale(word: str | None) -> str | None:
    if word is None:
        return None
    return next(scale for scale, words in SCALE_WORDS.items() if word.casefold() in words)
