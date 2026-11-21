from __future__ import annotations

from typing import Annotated, Self

from pydantic import ConfigDict, Field, model_validator

from app.core.errors import InvalidInput

from .base import ContractModel
from .open_work import TASK_KEY_MAX_CHARS, parse_task_key
from .open_work_translation_keys import TRANSLATE_TASK, TranslationLanguage
from .review_switch import APPROVED_STATUS, LIVE_UNREVIEWED_STATUS, REFUSED_STATUS, WAITING_STATUS
from .translation_passages import HASH_PATTERN, PASSAGE_TEXT_MAX_CHARS, PASSAGE_TEXTS_MAX, UNIT_KEY_MAX_CHARS

__all__ = [
    "LIVE_TRANSLATION_STATUSES",
    "SERVED_TRANSLATION_STATUSES",
    "SUPERSEDED_STATUS",
    "TRANSLATION_NOTE_MAX_CHARS",
    "TRANSLATION_PASSAGES_MAX",
    "TRANSLATION_STATUSES",
    "WAITING_TRANSLATION_STATUSES",
    "PageTranslationPart",
    "PassageTranslation",
    "task_problem",
]

TRANSLATION_PASSAGES_MAX = 40
TRANSLATION_NOTE_MAX_CHARS = 500
SUPERSEDED_STATUS = "SUPERSEDED"
TRANSLATION_STATUSES = (
    APPROVED_STATUS,
    LIVE_UNREVIEWED_STATUS,
    WAITING_STATUS,
    REFUSED_STATUS,
    SUPERSEDED_STATUS,
)
SERVED_TRANSLATION_STATUSES = (APPROVED_STATUS, LIVE_UNREVIEWED_STATUS)
WAITING_TRANSLATION_STATUSES = (WAITING_STATUS, LIVE_UNREVIEWED_STATUS)
LIVE_TRANSLATION_STATUSES = (APPROVED_STATUS, LIVE_UNREVIEWED_STATUS, WAITING_STATUS)
REPEATED = "each passage is translated once in a part; {key} is named twice"
OTHER_TASK = (
    "{key} is not the TRANSLATE task of this part: name TRANSLATE:{kind}:{slug}:{language}, or no task_key."
)

PassageText = Annotated[str, Field(max_length=PASSAGE_TEXT_MAX_CHARS)]


class PassageTranslation(ContractModel):
    model_config = ConfigDict(str_strip_whitespace=False)

    key: str = Field(min_length=1, max_length=UNIT_KEY_MAX_CHARS)
    source_hash: str = Field(pattern=HASH_PATTERN)
    texts: list[PassageText] = Field(min_length=1, max_length=PASSAGE_TEXTS_MAX)


class PageTranslationPart(ContractModel):
    language: TranslationLanguage
    passages: list[PassageTranslation] = Field(min_length=1, max_length=TRANSLATION_PASSAGES_MAX)
    task_key: str | None = Field(default=None, min_length=1, max_length=TASK_KEY_MAX_CHARS)
    note: str | None = Field(default=None, min_length=1, max_length=TRANSLATION_NOTE_MAX_CHARS)

    @model_validator(mode="after")
    def _each_passage_once(self) -> Self:
        seen: set[str] = set()
        for passage in self.passages:
            if passage.key in seen:
                raise ValueError(REPEATED.format(key=passage.key))
            seen.add(passage.key)
        return self


def task_problem(key: str | None, page: tuple[str, str], language: str) -> str | None:
    if key is None:
        return None
    try:
        task = parse_task_key(key)
    except InvalidInput as wrong:
        return str(wrong)
    kind, slug = page
    named = (task.kind, task.subject_kind, task.detail, (task.slug or "").casefold())
    if named != (TRANSLATE_TASK, kind, language, slug.casefold()):
        return OTHER_TASK.format(key=key, kind=kind, slug=slug, language=language)
    return None
