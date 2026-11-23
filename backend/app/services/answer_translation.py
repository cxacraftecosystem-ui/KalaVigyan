from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

from app.core.errors import AppError
from app.data.craft_text import script_of
from app.research.blocks_component import COMPONENT_KIND
from app.research.crafts import QUESTION_MAX_CHARS
from app.research.explainer import payload_sentences, with_payload_sentences
from app.research.terms import spans_still_shown
from app.research.translation import (
    TRANSLATION_ITEM_MAX_CHARS,
    TranslationItem,
    TranslationRequest,
    Translator,
)
from app.research.understanding import ENGLISH_QUESTION_MIN_CHARS, Understanding
from app.research.vocabulary import CANONICAL_LANGUAGE

__all__ = [
    "ENGLISH_SCRIPTS",
    "TERM_SEGMENT_PREFIX",
    "AnswerTranslation",
    "Segment",
    "TranslationCache",
    "english_question",
    "english_rendering",
    "needs_english_rendering",
    "translate_segments",
    "translated_block",
    "translated_sentences",
    "with_english_question",
]

logger = logging.getLogger(__name__)

ENGLISH_SCRIPTS = frozenset({"Latn", "Zyyy"})
QUESTION_KEY = "question"
TERM_SEGMENT_PREFIX = "term:"


class TranslationCache(Protocol):
    async def known(self, language: str, texts: Mapping[uuid.UUID, str]) -> dict[uuid.UUID, str]: ...

    async def remember(self, language: str, entries: Mapping[uuid.UUID, tuple[str, str]]) -> None: ...


@dataclass(frozen=True)
class AnswerTranslation:
    translator: Translator
    cache: TranslationCache


TITLE_KEY_SUFFIX = ".title"


@dataclass(frozen=True)
class Segment:
    key: str
    text: str
    claim_id: uuid.UUID | None = None


def needs_english_rendering(question: str) -> bool:
    return script_of(question) not in ENGLISH_SCRIPTS


async def english_question(question: str, translation: AnswerTranslation) -> str:
    if not needs_english_rendering(question):
        return question
    return await english_rendering(question, translation) or question


async def english_rendering(question: str, translation: AnswerTranslation) -> str | None:
    rendered = await _translated(
        [Segment(QUESTION_KEY, question)], CANONICAL_LANGUAGE, translation.translator
    )
    return rendered.get(QUESTION_KEY)


async def with_english_question(
    understanding: Understanding, *, question: str, language: str, translation: AnswerTranslation
) -> Understanding:
    if understanding.english_question is not None:
        return understanding
    if not needs_english_rendering(question):
        english = question if language == CANONICAL_LANGUAGE else None
    else:
        english = await english_rendering(question, translation)
    if english is None or not ENGLISH_QUESTION_MIN_CHARS <= len(english.strip()) <= QUESTION_MAX_CHARS:
        return understanding
    shown = understanding.model_dump(mode="json", by_alias=True)
    return Understanding.model_validate(shown | {"englishQuestion": english})


async def translated_sentences(
    sentences: Sequence[Mapping[str, Any]],
    *,
    language: str,
    translation: AnswerTranslation,
    claim_texts: Mapping[uuid.UUID, str],
    term_names: Mapping[str, Sequence[str]] | None = None,
) -> list[dict[str, Any]]:
    found = await translate_segments(
        _sentence_segments(sentences, claim_texts), language=language, translation=translation
    )
    renderings = _renderings(found, _term_surfaces(sentences))
    return [_translated_sentence(sentence, found, renderings, term_names or {}) for sentence in sentences]


async def translated_block(
    block: Mapping[str, Any],
    *,
    language: str,
    translation: AnswerTranslation,
    claim_texts: Mapping[uuid.UUID, str],
    term_names: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, Any]:
    titled = await _translated_title(block, language=language, translation=translation)
    sentences = payload_sentences(titled)
    if not sentences:
        return titled
    found = await translate_segments(
        _sentence_segments(sentences, claim_texts), language=language, translation=translation
    )
    renderings = _renderings(found, _term_surfaces(sentences))
    names = term_names or {}
    return with_payload_sentences(
        titled, lambda sentence: _translated_sentence(sentence, found, renderings, names)
    )


async def _translated_title(
    block: Mapping[str, Any], *, language: str, translation: AnswerTranslation
) -> dict[str, Any]:
    shown = dict(block)
    title = shown.get("title")
    if shown.get("kind") != COMPONENT_KIND or not isinstance(title, str):
        return shown
    key = f"{shown.get('id')}{TITLE_KEY_SUFFIX}"
    found = await translate_segments([Segment(key, title)], language=language, translation=translation)
    return shown | {"title": found[key]} if key in found else shown


async def translate_segments(
    segments: Sequence[Segment], *, language: str, translation: AnswerTranslation
) -> dict[str, str]:
    if language == CANONICAL_LANGUAGE or not segments:
        return {}
    cacheable = {segment.claim_id: segment.text for segment in segments if segment.claim_id is not None}
    cached = await translation.cache.known(language, cacheable) if cacheable else {}
    found = {s.key: cached[s.claim_id] for s in segments if s.claim_id is not None and s.claim_id in cached}
    pending = [segment for segment in segments if segment.key not in found]
    if not pending:
        return found
    fresh = await _translated(pending, language, translation.translator)
    learned = {
        s.claim_id: (s.text, fresh[s.key]) for s in pending if s.claim_id is not None and s.key in fresh
    }
    if learned:
        await translation.cache.remember(language, learned)
    return found | fresh


async def _translated(segments: Sequence[Segment], language: str, translator: Translator) -> dict[str, str]:
    items = [
        TranslationItem(key=segment.key, text=segment.text)
        for segment in segments
        if len(segment.text) <= TRANSLATION_ITEM_MAX_CHARS
    ]
    if not items:
        return {}
    try:
        return await translator.translate(TranslationRequest(language=language, items=items))
    except AppError as error:
        logger.warning("translation into %s failed, the original stays: %s", language, error)
        return {}


def _sentence_segments(
    sentences: Sequence[Mapping[str, Any]], claim_texts: Mapping[uuid.UUID, str]
) -> list[Segment]:
    shown = [Segment(s["id"], s["text"], _claim_of(s, claim_texts)) for s in sentences]
    surfaces = _term_surfaces(sentences)
    return [*shown, *(Segment(key, text) for text, key in surfaces.items())]


def _term_surfaces(sentences: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    texts = dict.fromkeys(span["text"] for sentence in sentences for span in sentence.get("terms", ()))
    return {text: f"{TERM_SEGMENT_PREFIX}{n}" for n, text in enumerate(texts, start=1)}


def _renderings(found: Mapping[str, str], surfaces: Mapping[str, str]) -> dict[str, str]:
    return {text: found[key] for text, key in surfaces.items() if key in found}


def _claim_of(sentence: Mapping[str, Any], claim_texts: Mapping[uuid.UUID, str]) -> uuid.UUID | None:
    claims = {citation["claimId"] for citation in sentence["citations"]}
    if len(claims) != 1:
        return None
    claim_id = uuid.UUID(claims.pop())
    return claim_id if claim_texts.get(claim_id) == sentence["text"] else None


def _translated_sentence(
    sentence: Mapping[str, Any],
    found: Mapping[str, str],
    renderings: Mapping[str, str],
    term_names: Mapping[str, Sequence[str]],
) -> dict[str, Any]:
    text = found.get(sentence["id"])
    if text is None:
        return dict(sentence)
    shown = {**sentence, "text": text, "translated": True, "original": sentence["text"]}
    if "terms" in sentence:
        shown["terms"] = spans_still_shown(text, sentence["terms"], renderings, term_names)
    return shown
