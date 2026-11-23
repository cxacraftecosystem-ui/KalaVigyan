from __future__ import annotations

from collections.abc import Collection, Iterable

from app.providers.elevenlabs import STT_LANGUAGE_CODES, TTS_LANGUAGES
from app.research.vocabulary import ANSWER_LANGUAGES, language_option

from .phrases import phrased_languages

__all__ = ["VOICE_LANGUAGES", "heard_and_spoken", "voice_language_options"]


def heard_and_spoken(
    candidates: Iterable[str], *, heard: Collection[str], spoken: Collection[str]
) -> tuple[str, ...]:
    return tuple(code for code in candidates if code in heard and code in spoken)


VOICE_LANGUAGES = phrased_languages(
    heard_and_spoken(ANSWER_LANGUAGES, heard=STT_LANGUAGE_CODES, spoken=TTS_LANGUAGES)
)


def voice_language_options() -> list[dict[str, str]]:
    return [language_option(code) for code in VOICE_LANGUAGES]
