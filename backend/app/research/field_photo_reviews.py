from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date
from typing import Literal, Self

from pydantic import AwareDatetime, Field, model_validator

from .base import ContractModel
from .field_voices import ARTISAN_IMAGE_VISIBILITIES, FIELD_LIST_PAGE_SIZE, FIELD_ORIGINS
from .image_screens import FACE, ID_DOCUMENT, NEAR_BITS, NEAR_DUPLICATE, SCREEN_FLAGS, SCREEN_VERDICTS

__all__ = [
    "CROP",
    "CROP_SIDE_MIN",
    "DECIDED_ACTION",
    "FIELD_PHOTO_QUEUE_SCHEMA_VERSION",
    "HIDDEN",
    "HIDE",
    "HIDE_REASONS",
    "HISTORY_SHOWN",
    "NOTE_MAX_CHARS",
    "NOTE_MIN_CHARS",
    "OTHER",
    "PHOTO_DECISIONS",
    "PHOTO_RISKS",
    "PHOTO_TARGET",
    "QUEUE_STATES",
    "SHOW",
    "SHOWING_DECISIONS",
    "SHOWN",
    "WAITING",
    "FieldPhotoItem",
    "FieldPhotoQueue",
    "PhotoCrop",
    "PhotoDecisionRequest",
    "PhotoDecisionView",
    "PhotoHistoryEntry",
    "PhotoPerson",
    "PhotoQueueCounts",
    "PhotoScreenView",
    "decision_problem",
    "master_flags",
    "photo_flags",
    "photo_risk",
]

FIELD_PHOTO_QUEUE_SCHEMA_VERSION = 1
SHOW = "SHOW"
HIDE = "HIDE"
CROP = "CROP"
PHOTO_DECISIONS = (SHOW, HIDE, CROP)
SHOWING_DECISIONS = (SHOW, CROP)
OTHER = "OTHER"
HIDE_REASONS = ("IDENTITY_DOCUMENT", "NOT_AGREED", "PRIVATE_PLACE", "POOR_QUALITY", "NOT_THIS_CRAFT", OTHER)
WAITING = "WAITING"
SHOWN = "SHOWN"
HIDDEN = "HIDDEN"
QUEUE_STATES = (WAITING, SHOWN, HIDDEN)
PHOTO_RISKS = ("IDENTITY", "FACE", "CHECK", "CLEAR")
NOTE_MIN_CHARS = 3
NOTE_MAX_CHARS = 500
CROP_SIDE_MIN = 64
HISTORY_SHOWN = 5
DECIDED_ACTION = "field_photo.decided"
PHOTO_TARGET = "FieldImage"
SHA256_PATTERN = r"^[0-9a-f]{64}$"


class PhotoCrop(ContractModel):
    left: int = Field(ge=0)
    top: int = Field(ge=0)
    width: int = Field(ge=CROP_SIDE_MIN)
    height: int = Field(ge=CROP_SIDE_MIN)

    def box(self) -> tuple[int, int, int, int]:
        return self.left, self.top, self.width, self.height

    def inside(self, width: int, height: int) -> bool:
        return self.left + self.width <= width and self.top + self.height <= height

    def leaves_out(self, width: int, height: int) -> bool:
        return self.width * self.height < width * height


class PhotoDecisionRequest(ContractModel):
    decision: Literal[*PHOTO_DECISIONS]
    seen_sha256: str = Field(pattern=SHA256_PATTERN)
    reason: Literal[*HIDE_REASONS] | None = None
    note: str | None = Field(default=None, max_length=NOTE_MAX_CHARS)
    crop: PhotoCrop | None = None
    clear_flags: bool = False

    @model_validator(mode="after")
    def _complete(self) -> Self:
        problem = decision_problem(self)
        if problem is not None:
            raise ValueError(problem)
        return self


def decision_problem(request: PhotoDecisionRequest) -> str | None:
    hiding = request.decision == HIDE
    noted = len((request.note or "").strip()) >= NOTE_MIN_CHARS
    if hiding and request.reason is None:
        return "Say why the photograph stays hidden."
    if not hiding and request.reason is not None:
        return "Only a photograph kept hidden takes a reason."
    if request.reason == OTHER and not noted:
        return "Say in a note why it stays hidden."
    if (request.decision == CROP) != (request.crop is not None):
        return "A crop gives the region to keep, and only a crop does."
    if request.clear_flags and request.decision != SHOW:
        return "A flag is cleared only to show the whole photograph."
    if request.clear_flags and not noted:
        return "Say in a note why the screen's flag is wrong."
    return None


def photo_flags(vision_flags: Sequence[str], distance: int | None) -> tuple[str, ...]:
    close = (NEAR_DUPLICATE,) if distance is not None and distance <= NEAR_BITS else ()
    return tuple(flag for flag in SCREEN_FLAGS if flag in (*vision_flags, *close))


def photo_risk(flags: Sequence[str] | None) -> str:
    if flags is None:
        return "CHECK"
    if ID_DOCUMENT in flags:
        return "IDENTITY"
    if FACE in flags:
        return "FACE"
    return "CHECK" if flags else "CLEAR"


def master_flags(flags: Sequence[str] | None, *, someone_named: bool) -> tuple[str, ...]:
    risky = (ID_DOCUMENT,) if someone_named else (ID_DOCUMENT, FACE)
    return tuple(flag for flag in flags or () if flag in risky)


class PhotoPerson(ContractModel):
    name: str | None
    kind: str | None


class PhotoScreenView(ContractModel):
    verdict: Literal[*SCREEN_VERDICTS]
    flags: list[str]
    reasons: list[str]
    nearest_distance: int | None
    model: str | None
    screened_at: AwareDatetime


class PhotoDecisionView(ContractModel):
    decision: Literal[*PHOTO_DECISIONS]
    reason: Literal[*HIDE_REASONS] | None
    note: str | None
    cleared_flags: list[str]
    crop: PhotoCrop | None
    crop_url: str | None
    decided_at: AwareDatetime
    decided_by: str | None
    decided_role: str
    current: bool


class PhotoHistoryEntry(ContractModel):
    decision: Literal[*PHOTO_DECISIONS]
    reason: str | None
    note: str | None
    decided_at: AwareDatetime
    decided_by: str | None


class FieldPhotoItem(ContractModel):
    id: uuid.UUID
    item_id: str = Field(min_length=3, max_length=200)
    origin: Literal[*FIELD_ORIGINS]
    publisher: str
    sha256: str = Field(pattern=SHA256_PATTERN)
    caption: str | None
    alt: str
    taken_on: date | None
    crafts: list[str]
    placements: list[str]
    people: list[PhotoPerson]
    credit: str
    workshop: str | None
    statement: str
    rights_holder: str
    licence: str | None
    width: int = Field(ge=1)
    height: int = Field(ge=1)
    mime: str
    file_url: str | None
    state: Literal[*QUEUE_STATES]
    risk: Literal[*PHOTO_RISKS]
    master_only: bool
    screen: PhotoScreenView | None
    decision: PhotoDecisionView | None
    history: list[PhotoHistoryEntry] = Field(max_length=HISTORY_SHOWN)


class PhotoQueueCounts(ContractModel):
    waiting: int = Field(ge=0)
    shown: int = Field(ge=0)
    hidden: int = Field(ge=0)


class FieldPhotoQueue(ContractModel):
    schema_version: Literal[1]
    state: Literal[*QUEUE_STATES]
    visibility: Literal[*ARTISAN_IMAGE_VISIBILITIES]
    counts: PhotoQueueCounts
    cursor: str | None
    next_cursor: str | None
    items: list[FieldPhotoItem] = Field(max_length=FIELD_LIST_PAGE_SIZE)
