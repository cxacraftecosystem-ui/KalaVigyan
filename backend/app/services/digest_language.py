from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from app.research.vocabulary import ANSWER_LANGUAGES, CANONICAL_LANGUAGE

from .answer_translation import AnswerTranslation, Segment, translate_segments

__all__ = ["DIGEST_SEGMENT_PREFIX", "DigestTranslations", "digest_language"]

DIGEST_SEGMENT_PREFIX = "digest:"


def digest_language(preferred: str | None) -> str:
    return preferred if preferred in ANSWER_LANGUAGES else CANONICAL_LANGUAGE


@dataclass
class DigestTranslations:
    translation: AnswerTranslation | None
    known: dict[tuple[str, str], str] = field(default_factory=dict)

    async def rendered(self, language: str, texts: Sequence[str]) -> dict[str, str]:
        if self.translation is None or language == CANONICAL_LANGUAGE:
            return {}
        pending = [text for text in dict.fromkeys(texts) if (language, text) not in self.known]
        segments = [Segment(f"{DIGEST_SEGMENT_PREFIX}{n}", text) for n, text in enumerate(pending)]
        found = await translate_segments(segments, language=language, translation=self.translation)
        self.known.update(
            {(language, segment.text): found[segment.key] for segment in segments if segment.key in found}
        )
        return {text: self.known[(language, text)] for text in texts if (language, text) in self.known}
