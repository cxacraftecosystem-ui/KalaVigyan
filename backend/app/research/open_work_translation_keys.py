from __future__ import annotations

from typing import Literal

from .vocabulary import ANSWER_LANGUAGES, CANONICAL_LANGUAGE

__all__ = [
    "TRANSLATE_TASK",
    "TRANSLATION_LANGUAGES",
    "TranslationLanguage",
    "is_translation_detail",
]

TRANSLATE_TASK = "TRANSLATE"
TRANSLATION_LANGUAGES = tuple(language for language in ANSWER_LANGUAGES if language != CANONICAL_LANGUAGE)

TranslationLanguage = Literal[*TRANSLATION_LANGUAGES]


def is_translation_detail(detail: str) -> bool:
    return detail in TRANSLATION_LANGUAGES
