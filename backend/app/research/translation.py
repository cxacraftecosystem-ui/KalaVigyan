from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from types import MappingProxyType
from typing import Protocol, Self, runtime_checkable

from pydantic import Field, model_validator

from .base import ContractModel
from .hedges import hedges_in
from .quotes import formulas_in, normalise_quote_text, numbers_in
from .stance_markers import hedge_marked, negation_marked
from .vocabulary import ANSWER_LANGUAGE_SPECS, CANONICAL_LANGUAGE, AnswerLanguage

__all__ = [
    "NUMBER_UNITS",
    "SCRIPT_LETTER_NAMES",
    "SYMBOL_UNITS",
    "TARGET_SCRIPT_MIN_SHARE",
    "TRANSLATION_ATTEMPTS",
    "TRANSLATION_ITEMS_MAX",
    "TRANSLATION_ITEM_MAX_CHARS",
    "TRANSLATION_KEY_MAX_CHARS",
    "TranslationItem",
    "TranslationRequest",
    "Translator",
    "protected_tokens",
    "translation_problems",
    "written_in",
]

TRANSLATION_ATTEMPTS = 2
TRANSLATION_ITEMS_MAX = 200
TRANSLATION_ITEM_MAX_CHARS = 1000
TRANSLATION_KEY_MAX_CHARS = 60
TARGET_SCRIPT_MIN_SHARE = 0.5
SYMBOL_UNITS = ("°C", "°F", "%", "‰")
NUMBER_UNITS = (
    "kJ/mol",
    "g/cm3",
    "mg/L",
    "mol/L",
    "g/L",
    "km2",
    "cm3",
    "m2",
    "m3",
    "kg",
    "mg",
    "μg",
    "km",
    "cm",
    "mm",
    "μm",
    "nm",
    "mL",
    "ml",
    "kPa",
    "MPa",
    "Pa",
    "atm",
    "bar",
    "kJ",
    "kW",
    "Hz",
    "ppm",
    "ppb",
    "mol",
    "min",
    "ha",
    "g",
    "m",
    "L",
    "J",
    "W",
    "V",
    "K",
    "h",
    "s",
)
SCRIPT_LETTER_NAMES: Mapping[str, str] = MappingProxyType(
    {
        "Latn": "LATIN",
        "Deva": "DEVANAGARI",
        "Beng": "BENGALI",
        "Taml": "TAMIL",
        "Telu": "TELUGU",
        "Gujr": "GUJARATI",
        "Knda": "KANNADA",
        "Mlym": "MALAYALAM",
        "Orya": "ORIYA",
        "Guru": "GURMUKHI",
        "Arab": "ARABIC",
    }
)
MHCHEM = re.compile(r"\\(?:ce|pu)\{(?:[^{}]|\{[^{}]*\})*\}")
PH = re.compile(r"(?<![A-Za-z])pH(?![A-Za-z])")
SYMBOL_UNIT = re.compile("|".join(re.escape(unit) for unit in SYMBOL_UNITS))
NUMBER_UNIT = re.compile(r"\d\s?(" + "|".join(re.escape(unit) for unit in NUMBER_UNITS) + r")(?![^\W\d_])")


class TranslationItem(ContractModel):
    key: str = Field(min_length=1, max_length=TRANSLATION_KEY_MAX_CHARS)
    text: str = Field(min_length=1, max_length=TRANSLATION_ITEM_MAX_CHARS)


class TranslationRequest(ContractModel):
    language: AnswerLanguage
    items: list[TranslationItem] = Field(min_length=1, max_length=TRANSLATION_ITEMS_MAX)

    @model_validator(mode="after")
    def _keys_are_unique(self) -> Self:
        keys = [item.key for item in self.items]
        if len(keys) != len(set(keys)):
            raise ValueError("translation item keys are unique")
        return self


def protected_tokens(text: str) -> set[str]:
    normalised = normalise_quote_text(text)
    found = {match.group() for match in MHCHEM.finditer(normalised)}
    found |= set(formulas_in(text))
    found |= {match.group() for match in SYMBOL_UNIT.finditer(normalised)}
    found |= {match.group(1) for match in NUMBER_UNIT.finditer(normalised)}
    found |= {match.group() for match in PH.finditer(normalised)}
    return found


def written_in(text: str, script: str) -> bool:
    prefix = SCRIPT_LETTER_NAMES[script]
    letters = _letters(text)
    if not letters:
        return False
    inside = sum(1 for char in letters if unicodedata.name(char, "").startswith(prefix))
    return inside / len(letters) >= TARGET_SCRIPT_MIN_SHARE


def translation_problems(original: str, translated: str, *, language: str) -> list[str]:
    if not translated.strip():
        return ["the translation is empty"]
    problems: list[str] = []
    source, target = set(numbers_in(original)), set(numbers_in(translated))
    problems += [f"number {number} is missing" for number in sorted(source - target)]
    problems += [f"number {number} is not in the original" for number in sorted(target - source)]
    kept, made = protected_tokens(original), protected_tokens(translated)
    problems += [f"{token} must be copied exactly" for token in sorted(kept - made)]
    problems += [f"{token} is not in the original" for token in sorted(made - kept)]
    script = ANSWER_LANGUAGE_SPECS[language].script
    if _letters(_prose(original, kept)) and not written_in(_prose(translated, made), script):
        problems.append(f"the translation is not written in the {script} script")
    return problems + _stance_problems(original, translated, language)


def _stance_problems(original: str, translated: str, language: str) -> list[str]:
    problems: list[str] = []
    if negation_marked(original, CANONICAL_LANGUAGE) and not negation_marked(translated, language):
        problems.append("the original's negation (not, no, never, without) is missing")
    hedges = hedges_in(original)
    if hedges and not hedge_marked(translated, language):
        problems.append(f"the original's hedge ({', '.join(hedges)}) is missing")
    return problems


def _prose(text: str, tokens: set[str]) -> str:
    prose = normalise_quote_text(text)
    for token in sorted(tokens, key=len, reverse=True):
        prose = prose.replace(token, " ")
    return prose


def _letters(text: str) -> list[str]:
    return [char for char in text if char.isalpha()]


@runtime_checkable
class Translator(Protocol):
    async def translate(self, request: TranslationRequest) -> dict[str, str]: ...
