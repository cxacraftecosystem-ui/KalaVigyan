from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from app.research.vocabulary import ANSWER_LANGUAGES, CANONICAL_LANGUAGE
from app.services.interface_words import written_words

__all__ = [
    "END_CALL_REPLIES",
    "FILLERS",
    "NO_CRAFT_REPLIES",
    "NO_EVIDENCE_REPLIES",
    "PHRASE_TABLES",
    "SOURCE_WORDS",
    "UNSAID_REPLIES",
    "phrase",
    "phrased_languages",
]

FILLER = "Let me check the sources... "
NO_EVIDENCE = "I found no cited answer to that about {craft} yet."
NO_CRAFT = "Which craft do you mean? Name it and ask again."
UNSAID = "I could not prepare that answer just now. Please ask again."
QUOTA_END = "That is all the voice time for today."
TURNS_END = "That is the end of this call."
SOURCE_WORD = ("Source", "Sources")


def _table(key: str, english: str) -> Mapping[str, str]:
    others = (code for code in ANSWER_LANGUAGES if code != CANONICAL_LANGUAGE)
    written = {code: written_words(code).shown(key, english) for code in others}
    return MappingProxyType({CANONICAL_LANGUAGE: english, **{c: text for c, text in written.items() if text}})


FILLERS = _table("voice.filler", FILLER)
NO_EVIDENCE_REPLIES = _table("voice.noEvidence", NO_EVIDENCE)
NO_CRAFT_REPLIES = _table("voice.noCraft", NO_CRAFT)
UNSAID_REPLIES = _table("voice.unsaid", UNSAID)
END_CALL_REPLIES: Mapping[str, Mapping[str, str]] = MappingProxyType(
    {"quota": _table("voice.endCall", QUOTA_END), "turns": _table("voice.endCall", TURNS_END)}
)
_SOURCE_WORDS = tuple(_table("voice.sourceWord", word) for word in SOURCE_WORD)
SOURCE_WORDS: Mapping[str, tuple[str, str]] = MappingProxyType(
    {
        language: (one, _SOURCE_WORDS[1][language])
        for language, one in _SOURCE_WORDS[0].items()
        if language in _SOURCE_WORDS[1]
    }
)
PHRASE_TABLES: tuple[Mapping[str, str], ...] = (
    FILLERS,
    NO_EVIDENCE_REPLIES,
    NO_CRAFT_REPLIES,
    UNSAID_REPLIES,
    *END_CALL_REPLIES.values(),
)


def phrased_languages(candidates: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(
        language
        for language in candidates
        if language in SOURCE_WORDS and all(language in t for t in PHRASE_TABLES)
    )


def phrase(table: Mapping[str, str], language: str, **values: str) -> str:
    return table[language].format(**values)
