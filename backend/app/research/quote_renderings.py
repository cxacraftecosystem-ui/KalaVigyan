from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from types import MappingProxyType

from .translation import (
    TRANSLATION_ITEM_MAX_CHARS,
    TRANSLATION_ITEMS_MAX,
    TranslationItem,
    TranslationRequest,
    Translator,
    translation_problems,
)
from .vocabulary import CANONICAL_LANGUAGE

__all__ = [
    "NO_RENDERINGS",
    "QuotedIn",
    "english_renderings",
    "read_as",
    "rendering_problems",
]

NO_RENDERINGS: Mapping[str, str] = MappingProxyType({})


@dataclass(frozen=True)
class QuotedIn:
    text: str
    language: str

    @property
    def foreign(self) -> bool:
        return self.language != CANONICAL_LANGUAGE and bool(self.text.strip())


def rendering_problems(quote: QuotedIn, rendered: str) -> list[str]:
    return translation_problems(
        quote.text, rendered, language=CANONICAL_LANGUAGE, source_language=quote.language
    )


def read_as(quotes: Iterable[str], renderings: Mapping[str, str]) -> list[str]:
    return [renderings.get(quote, quote) for quote in quotes]


async def english_renderings(quotes: Iterable[QuotedIn], translator: Translator) -> dict[str, str]:
    foreign = list({quote.text: quote for quote in quotes if _translatable(quote)}.values())
    renderings: dict[str, str] = {}
    for start in range(0, len(foreign), TRANSLATION_ITEMS_MAX):
        batch = foreign[start : start + TRANSLATION_ITEMS_MAX]
        renderings.update(await _rendered(batch, translator))
    return renderings


async def _rendered(batch: list[QuotedIn], translator: Translator) -> dict[str, str]:
    keyed = {f"q{number}": quote for number, quote in enumerate(batch)}
    items = [TranslationItem(key=key, text=quote.text) for key, quote in keyed.items()]
    replies = await translator.translate(TranslationRequest(language=CANONICAL_LANGUAGE, items=items))
    return {
        quote.text: replies[key]
        for key, quote in keyed.items()
        if key in replies and not rendering_problems(quote, replies[key])
    }


def _translatable(quote: QuotedIn) -> bool:
    return quote.foreign and len(quote.text) <= TRANSLATION_ITEM_MAX_CHARS
