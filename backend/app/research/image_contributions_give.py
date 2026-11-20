from __future__ import annotations

import uuid
from typing import Literal, Self

from pydantic import Field, model_validator

from .base import ContractModel, HttpsUrl
from .image_contributions import BatchPicture, ImageContributionStatus
from .image_intake_fetch import IMAGE_BASE64_BYTES_MAX, base64_chars_max
from .image_screens import ScreenSummary
from .upload_links import SlotCraft

__all__ = [
    "CONFIRMATION_MAX_CHARS",
    "GIVEN_BASE64_BYTES_MAX",
    "GIVE_SCHEMA_VERSION",
    "GivenItem",
    "GivenPicture",
    "GivenPictures",
    "PictureSource",
    "given_next_step",
    "source_problem",
]

GIVE_SCHEMA_VERSION = 1
CONFIRMATION_MAX_CHARS = 500
GIVEN_BASE64_BYTES_MAX = 12 * 1024 * 1024
ONE_SOURCE = "Give the picture as image_url or as image_base64, exactly one of them"
SHOWN = "Every picture given is shown once it is approved: open my pictures on the site to follow each one."
WAITING = "A picture waits for an Admin's review; a picture flagged by the screen always does."
NONE_GIVEN = "No picture was given: read each one's refusal, fix it and call again."


class PictureSource(ContractModel):
    image_url: HttpsUrl | None = Field(
        default=None, description="An https link to the picture itself; KalaVigyan's server fetches it"
    )
    image_base64: str | None = Field(
        default=None,
        min_length=8,
        max_length=base64_chars_max(IMAGE_BASE64_BYTES_MAX) + 64,
        description="The picture's bytes in base64, or a data: URI, at most 6 MB before encoding",
    )

    @model_validator(mode="after")
    def _one_source(self) -> Self:
        problem = source_problem(self.image_url, self.image_base64)
        if problem:
            raise ValueError(problem)
        return self


def source_problem(image_url: str | None, image_base64: str | None) -> str | None:
    return ONE_SOURCE if (image_url is None) == (image_base64 is None) else None


class GivenItem(BatchPicture, PictureSource):
    pass


class GivenPicture(ContractModel):
    position: int = Field(ge=1)
    contribution_id: uuid.UUID | None = None
    status: ImageContributionStatus | None = None
    label: str | None = None
    received: str | None = None
    mime: str | None = None
    width: int | None = None
    height: int | None = None
    screen: ScreenSummary | None = None
    refused: str | None = None


class GivenPictures(ContractModel):
    schema_version: Literal[1] = GIVE_SCHEMA_VERSION
    craft: SlotCraft
    declaration_id: uuid.UUID | None
    given: int = Field(ge=0)
    refused: int = Field(ge=0)
    pictures: list[GivenPicture]
    next_step: str


def given_next_step(given: int, approved: int) -> str:
    if given == 0:
        return NONE_GIVEN
    return SHOWN if given == approved else f"{WAITING} {SHOWN}"
