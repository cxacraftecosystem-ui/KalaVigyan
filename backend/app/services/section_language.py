from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import TypeAdapter

from app.research.explainer import Block
from app.research.vocabulary import CANONICAL_LANGUAGE

from .answer_translation import AnswerTranslation, translated_block, translated_sentences
from .explainer_events import ExplainerStream

__all__ = ["block_in_language", "open_questions_in_language"]

BLOCKS = TypeAdapter(Block)


async def block_in_language(
    block: Block,
    *,
    stream: ExplainerStream,
    translation: AnswerTranslation,
    claim_texts: Mapping[uuid.UUID, str],
    term_names: Mapping[str, Sequence[str]] | None = None,
) -> Block:
    if stream.language == CANONICAL_LANGUAGE:
        return block
    await stream.status("TRANSLATING")
    payload = block.model_dump(mode="json", by_alias=True, exclude_unset=True)
    shown = await translated_block(
        payload,
        language=stream.language,
        translation=translation,
        claim_texts=claim_texts,
        term_names=term_names,
    )
    return BLOCKS.validate_python(shown)


async def open_questions_in_language(
    sentences: Sequence[dict[str, Any]],
    *,
    stream: ExplainerStream,
    translation: AnswerTranslation,
    claim_texts: Mapping[uuid.UUID, str],
) -> list[dict[str, Any]]:
    if stream.language == CANONICAL_LANGUAGE or not sentences:
        return list(sentences)
    await stream.status("TRANSLATING")
    return await translated_sentences(
        sentences, language=stream.language, translation=translation, claim_texts=claim_texts
    )
