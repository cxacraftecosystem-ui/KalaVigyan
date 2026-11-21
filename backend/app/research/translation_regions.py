from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType

from .open_work import PRIORITIES
from .vocabulary import ANSWER_LANGUAGES

__all__ = ["HINDI", "STATE_LANGUAGES", "home_languages", "offered_languages", "translation_priority"]

HINDI = "hi"
STATE_LANGUAGES: Mapping[str, str] = MappingProxyType(
    {
        "andhra pradesh": "te",
        "assam": "as",
        "bihar": "hi",
        "chhattisgarh": "hi",
        "delhi": "hi",
        "gujarat": "gu",
        "haryana": "hi",
        "himachal pradesh": "hi",
        "jammu and kashmir": "ur",
        "jharkhand": "hi",
        "karnataka": "kn",
        "kerala": "ml",
        "madhya pradesh": "hi",
        "maharashtra": "mr",
        "odisha": "or",
        "puducherry": "ta",
        "punjab": "pa",
        "rajasthan": "hi",
        "tamil nadu": "ta",
        "telangana": "te",
        "tripura": "bn",
        "uttar pradesh": "hi",
        "uttarakhand": "hi",
        "west bengal": "bn",
    }
)


def home_languages(states: Sequence[str]) -> tuple[str, ...]:
    found = (STATE_LANGUAGES.get(" ".join(state.casefold().split())) for state in states)
    return tuple(dict.fromkeys(language for language in found if language in ANSWER_LANGUAGES))


def offered_languages(states: Sequence[str]) -> tuple[str, ...]:
    home = home_languages(states)
    return home if HINDI in home else (*home, HINDI)


def translation_priority(subject_priority: str, language: str, states: Sequence[str]) -> str:
    if language in home_languages(states):
        return subject_priority
    rank = min(PRIORITIES.index(subject_priority) + 1, len(PRIORITIES) - 1)
    return PRIORITIES[rank]
