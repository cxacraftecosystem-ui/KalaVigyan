from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import replace
from types import MappingProxyType

from app.research.composition import ComposeCandidate
from app.research.quote_renderings import QuotedIn, english_renderings
from app.research.translation import Translator, written_in
from app.research.vocabulary import ANSWER_LANGUAGE_SPECS, CANONICAL_LANGUAGE

from .drafts import DraftAnswer, DraftSection, DraftSentence, sentence_problems

__all__ = ["LANGUAGES_BY_SCRIPT", "RENDERED_QUOTES_MAX", "foreign_quotes", "quote_language", "rendered_draft"]

RENDERED_QUOTES_MAX = 8
LANGUAGES_BY_SCRIPT: Mapping[str, tuple[str, ...]] = MappingProxyType(
    {
        script: tuple(code for code, spec in ANSWER_LANGUAGE_SPECS.items() if spec.script == script)
        for script in dict.fromkeys(
            spec.script for code, spec in ANSWER_LANGUAGE_SPECS.items() if code != CANONICAL_LANGUAGE
        )
    }
)


def quote_language(ref: str, text: str) -> str | None:
    for script, languages in LANGUAGES_BY_SCRIPT.items():
        if not written_in(text, script):
            continue
        if len(languages) == 1:
            return languages[0]
        parts = ref.split(":")
        return parts[1] if len(parts) > 2 and parts[1] in languages else None
    return None


def foreign_quotes(sentences: Sequence[DraftSentence]) -> list[QuotedIn]:
    found: dict[str, QuotedIn] = {}
    for draft in sentences:
        for span in draft.sentence.spans if draft.sentence is not None else ():
            language = quote_language(span.ref, span.text)
            if language is not None:
                found.setdefault(span.text, QuotedIn(span.text, language))
    return list(found.values())[:RENDERED_QUOTES_MAX]


async def rendered_draft(
    draft: DraftAnswer, allowed: Mapping[str, ComposeCandidate], translator: Translator | None
) -> DraftAnswer:
    quotes = foreign_quotes(draft.failed) if translator is not None else []
    if translator is None or not quotes:
        return draft
    renderings = await english_renderings(quotes, translator)
    if not renderings:
        return draft
    sections = tuple(
        DraftSection(section.heading, tuple(_rechecked(s, allowed, renderings) for s in section.sentences))
        for section in draft.sections
    )
    return replace(draft, sections=sections, renderings={**draft.renderings, **renderings})


def _rechecked(
    draft: DraftSentence, allowed: Mapping[str, ComposeCandidate], renderings: Mapping[str, str]
) -> DraftSentence:
    if draft.passes or draft.sentence is None:
        return draft
    if sentence_problems(draft.sentence, allowed, renderings):
        return draft
    return replace(draft, problems=())
