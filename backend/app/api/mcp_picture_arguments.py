from __future__ import annotations

import uuid
from typing import Literal, Self

from pydantic import Field, ValidationError, model_validator

from app.core.errors import InvalidInput
from app.research.base import ContractModel, HttpsUrl
from app.research.crafts import SLUG_MAX_CHARS
from app.research.image_contributions import (
    BATCH_PICTURES_MAX,
    CLAIMS_MAX,
    IMAGE_TEXT_MAX_CHARS,
    PROMPT_MAX_CHARS,
    BatchPicture,
    PictureTarget,
    SharedDeclaration,
)
from app.research.image_contributions_give import CONFIRMATION_MAX_CHARS, GIVEN_BASE64_BYTES_MAX, GivenPicture
from app.research.image_intake_fetch import IMAGE_BASE64_BYTES_MAX, base64_chars_max
from app.research.upload_links import SlotCraft, SlotDeclaration, UploadSlot, UploadStart

from .mcp_picture_texts import CONFIRMATION_FIELD, DECLARATION_FIELD
from .mcp_studio_arguments import StudioArguments

__all__ = [
    "GivePictures",
    "GivenOrUploaded",
    "PicturesReply",
    "UploadPlace",
    "slot_declaration",
    "upload_slot",
]

ONE_WAY = "give each picture as image_url, image_base64 or upload true, exactly one of them"
NEEDS_WORDS = "a picture given in the call carries its caption and alt_text"
NEEDS_FACTS = "an uploaded picture names the facts it shows (claim_ids)"
NEEDS_DECLARATION = (
    "pictures given in the call need the declaration the person confirmed in the chat and their words of "
    "confirmation"
)
TOO_MUCH_BASE64 = (
    f"The pictures sent in one call are at most {GIVEN_BASE64_BYTES_MAX // (1024 * 1024)} MB together"
)


class GivenOrUploaded(PictureTarget):
    image_url: HttpsUrl | None = Field(
        default=None, description="An https link to the picture itself, at most 10 MB; the server fetches it"
    )
    image_base64: str | None = Field(
        default=None,
        min_length=8,
        max_length=base64_chars_max(IMAGE_BASE64_BYTES_MAX) + 64,
        description="The picture's bytes in base64 or a data: URI, at most 6 MB before encoding",
    )
    upload: bool = Field(default=False, description="True for a single-use upload slot instead")
    claim_ids: list[uuid.UUID] = Field(
        default_factory=list, max_length=CLAIMS_MAX, description="The facts the picture shows, from get_facts"
    )
    caption: str | None = Field(default=None, min_length=3, max_length=IMAGE_TEXT_MAX_CHARS)
    alt_text: str | None = Field(default=None, min_length=3, max_length=IMAGE_TEXT_MAX_CHARS)
    prompt: str | None = Field(
        default=None, min_length=1, max_length=PROMPT_MAX_CHARS, description="An AI image's prompt"
    )

    @model_validator(mode="after")
    def _one_way(self) -> Self:
        ways = [self.image_url is not None, self.image_base64 is not None, self.upload]
        if sum(ways) != 1:
            raise ValueError(ONE_WAY)
        if not self.upload and (self.caption is None or self.alt_text is None):
            raise ValueError(NEEDS_WORDS)
        if self.upload and not self.claim_ids:
            raise ValueError(NEEDS_FACTS)
        return self

    def batch_picture(self) -> BatchPicture:
        return BatchPicture.model_validate(self.model_dump(exclude={"image_url", "image_base64", "upload"}))


class GivePictures(StudioArguments):
    craft_slug: str = Field(min_length=1, max_length=SLUG_MAX_CHARS, description="A slug from find_crafts")
    declaration: SharedDeclaration | None = Field(default=None, description=DECLARATION_FIELD)
    confirmation: str | None = Field(
        default=None, min_length=2, max_length=CONFIRMATION_MAX_CHARS, description=CONFIRMATION_FIELD
    )
    pictures: list[GivenOrUploaded] = Field(min_length=1, max_length=BATCH_PICTURES_MAX)

    @model_validator(mode="after")
    def _declared_and_small(self) -> Self:
        sent = sum(len(picture.image_base64 or "") for picture in self.pictures)
        if sent > base64_chars_max(GIVEN_BASE64_BYTES_MAX):
            raise ValueError(TOO_MUCH_BASE64)
        given = any(not picture.upload for picture in self.pictures)
        if given and (self.declaration is None or self.confirmation is None):
            raise ValueError(NEEDS_DECLARATION)
        return self

    def placed(self, uploaded: bool) -> list[tuple[int, GivenOrUploaded]]:
        return [
            (at, picture) for at, picture in enumerate(self.pictures, start=1) if picture.upload is uploaded
        ]


class UploadPlace(ContractModel):
    position: int = Field(ge=1)
    upload: UploadStart | None = None
    refused: str | None = None


class PicturesReply(ContractModel):
    schema_version: Literal[1] = 1
    craft: SlotCraft | None = None
    declaration_id: uuid.UUID | None = None
    given: int = Field(default=0, ge=0)
    refused: int = Field(default=0, ge=0)
    pictures: list[GivenPicture] = Field(default_factory=list)
    uploads: list[UploadPlace] = Field(default_factory=list)
    next_step: str


def upload_slot(craft_slug: str, picture: GivenOrUploaded) -> UploadSlot:
    fields = {"stage_id", "material_id", "slot", "task_key", "claim_ids"}
    try:
        return UploadSlot.model_validate({"craft_slug": craft_slug, **picture.model_dump(include=fields)})
    except ValidationError as refused:
        raise InvalidInput(_said(refused)) from None


def slot_declaration(shared: SharedDeclaration | None, picture: GivenOrUploaded) -> SlotDeclaration | None:
    if shared is None:
        return None
    try:
        return SlotDeclaration.model_validate(
            {
                **shared.model_dump(),
                "prompt": picture.prompt,
                "caption": picture.caption,
                "alt_text": picture.alt_text,
            }
        )
    except ValidationError as refused:
        raise InvalidInput(_said(refused)) from None


def _said(refused: ValidationError) -> str:
    return "; ".join(str(problem["msg"]) for problem in refused.errors())
