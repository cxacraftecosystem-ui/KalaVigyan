from __future__ import annotations

import uuid
from typing import Literal

from pydantic import Field

from app.research.citations import Citation
from app.research.crafts import CraftRef
from app.research.testimony import (
    CLAIM_TEXT_MAX,
    CONCEPT_NAME_MAX,
    CONTRIBUTION_STATUSES,
    ENGLISH_MAX,
    LOCATOR_PRECISIONS,
    QUOTE_MAX_CHARS,
    TESTIMONY_CONCEPT_TYPES,
    TESTIMONY_ENGLISH_SOURCES,
    TESTIMONY_REJECT_REASONS,
    TESTIMONY_SCREENS,
)
from app.research.vocabulary import Discipline

from .common import APIModel

__all__ = [
    "ContributionOut",
    "ContributionsOut",
    "EditBody",
    "ReviewItemOut",
    "WithdrawnContributionOut",
]


class EditBody(APIModel):
    version: int = Field(ge=1)
    quote: str | None = Field(default=None, min_length=1, max_length=QUOTE_MAX_CHARS)
    english: str | None = Field(default=None, min_length=1, max_length=ENGLISH_MAX)
    englishChecked: bool = False
    claimText: str | None = Field(default=None, min_length=1, max_length=CLAIM_TEXT_MAX)
    discipline: Discipline | None = None
    conceptType: Literal[*TESTIMONY_CONCEPT_TYPES] | None = None
    conceptName: str | None = Field(default=None, min_length=1, max_length=CONCEPT_NAME_MAX)


Status = Literal[*CONTRIBUTION_STATUSES]
EnglishSource = Literal[*TESTIMONY_ENGLISH_SOURCES]


class SpeakerOut(APIModel):
    name: str | None
    role: Literal["ARTISAN"]
    district: str | None
    state: str | None


class AudioOut(APIModel):
    url: str
    expiresAt: str
    mimeType: str
    startMs: int = Field(ge=0)
    endMs: int = Field(ge=0)


class TurnBeforeOut(APIModel):
    text: str | None
    english: str | None
    answerId: str | None


class ContextOut(APIModel):
    before: TurnBeforeOut
    turnText: str | None
    audio: AudioOut | None


class ReviewItemOut(APIModel):
    id: uuid.UUID
    version: int = Field(ge=1)
    status: Status
    craft: CraftRef
    discipline: Discipline
    conceptType: Literal[*TESTIMONY_CONCEPT_TYPES]
    conceptName: str
    claimText: str | None
    quote: str | None
    language: str
    script: str
    direction: Literal["ltr", "rtl"]
    english: str | None
    englishSource: EnglishSource
    locator: str
    locatorPrecision: Literal[*LOCATOR_PRECISIONS]
    recordedAt: str
    speaker: SpeakerOut
    line: str
    screens: list[Literal[*TESTIMONY_SCREENS]]
    corroboratedBy: list[Citation]
    context: ContextOut
    submittedAt: str
    reviewedAt: str | None
    reviewerRole: str | None
    rejectReason: Literal[*TESTIMONY_REJECT_REASONS] | None
    reviewNote: str | None


class ContributionOut(APIModel):
    id: uuid.UUID
    status: Literal["PENDING", "APPROVED", "REJECTED"]
    conversationId: uuid.UUID
    craft: CraftRef
    discipline: Discipline
    claimText: str | None
    quote: str | None
    language: str
    english: str | None
    englishSource: EnglishSource
    locator: str
    recordedAt: str
    line: str
    submittedAt: str
    reviewedAt: str | None
    reviewerRole: str | None
    rejectReason: Literal[*TESTIMONY_REJECT_REASONS] | None
    reviewNote: str | None
    approvedAt: str | None
    withdrawnAt: None


class WithdrawnContributionOut(APIModel):
    id: uuid.UUID
    status: Literal["WITHDRAWN"]
    conversationId: uuid.UUID
    withdrawnAt: str


class ContributionsOut(APIModel):
    counts: dict[Literal["pending", "approved", "rejected", "withdrawn"], int]
    items: list[ContributionOut | WithdrawnContributionOut]
