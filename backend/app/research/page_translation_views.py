from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import ConfigDict, Field

from .base import ContractModel, absent
from .document_translation import SCRIPT_CODE
from .open_work_translation_keys import TranslationLanguage
from .page_proposals import PageSubject
from .page_translation_gates import TranslationCheck
from .page_translations import TRANSLATION_NOTE_MAX_CHARS, TRANSLATION_STATUSES
from .translation_passages import TaskPassage
from .vocabulary import TextDirection

__all__ = [
    "HELD",
    "PASSAGES_LIMIT_DEFAULT",
    "PASSAGES_LIMIT_MAX",
    "PASSAGE_STATES",
    "TO_TRANSLATE",
    "TRANSLATED",
    "TRANSLATION_VIEW_SCHEMA_VERSION",
    "WAITING",
    "LanguageOffer",
    "PageLanguages",
    "PassageView",
    "ReaderLanguages",
    "ReviewItem",
    "ReviewList",
    "ReviewNote",
    "TranslationView",
]

TRANSLATION_VIEW_SCHEMA_VERSION = 1
PASSAGES_LIMIT_DEFAULT = 40
PASSAGES_LIMIT_MAX = 200
PASSAGE_STATES = ("TO_TRANSLATE", "HELD", "WAITING", "TRANSLATED")
TO_TRANSLATE, HELD, WAITING, TRANSLATED = PASSAGE_STATES

PassageState = Literal[*PASSAGE_STATES]


class LanguageOffer(ContractModel):
    code: TranslationLanguage
    label: str
    autonym: str
    script: str = Field(pattern=SCRIPT_CODE)
    direction: TextDirection


class PassageView(TaskPassage):
    model_config = ConfigDict(str_strip_whitespace=False)

    chapter: str
    tag: str
    state: PassageState
    translation: list[str] | None = Field(default=None, exclude_if=absent)
    previous: list[str] | None = Field(default=None, exclude_if=absent)


class TranslationView(ContractModel):
    schema_version: Literal[1] = TRANSLATION_VIEW_SCHEMA_VERSION
    subject: PageSubject
    title: str
    language: LanguageOffer
    english_version: int = Field(ge=1)
    passages_total: int = Field(ge=0)
    translated: int = Field(ge=0)
    held: int = Field(ge=0)
    waiting: int = Field(ge=0)
    to_translate: int = Field(ge=0)
    offered: bool
    passages: list[PassageView]
    next_offset: int | None = None
    page_url: str


class PageLanguage(LanguageOffer):
    passages: int = Field(ge=0)
    translated: int = Field(ge=0)
    offered: bool


class PageLanguages(ContractModel):
    schema_version: Literal[1] = TRANSLATION_VIEW_SCHEMA_VERSION
    subject: PageSubject
    languages: list[PageLanguage]


class ReviewItem(ContractModel):
    model_config = ConfigDict(str_strip_whitespace=False)

    id: uuid.UUID
    subject: PageSubject
    language: TranslationLanguage
    key: str
    status: Literal[*TRANSLATION_STATUSES]
    english: str
    texts: list[str]
    current: bool
    checks: list[TranslationCheck]
    note: str | None = None
    created_at: datetime
    page_url: str


class ReviewList(ContractModel):
    schema_version: Literal[1] = TRANSLATION_VIEW_SCHEMA_VERSION
    languages: list[TranslationLanguage]
    total: int = Field(ge=0)
    items: list[ReviewItem]


class ReaderLanguages(ContractModel):
    languages: list[TranslationLanguage] = Field(max_length=16)


class ReviewNote(ContractModel):
    note: str | None = Field(default=None, min_length=1, max_length=TRANSLATION_NOTE_MAX_CHARS)
