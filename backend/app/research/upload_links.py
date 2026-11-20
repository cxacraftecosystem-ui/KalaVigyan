from __future__ import annotations

import uuid
from datetime import datetime, timedelta
from typing import Literal, Self
from urllib.parse import quote, urlencode

from pydantic import Field, model_validator

from .base import ContractModel
from .crafts import SLUG_MAX_CHARS
from .image_contributions import (
    CLAIMS_MAX,
    GENERATOR_MAX_CHARS,
    IMAGE_TEXT_MAX_CHARS,
    PROMPT_MAX_CHARS,
    ImageDeclaration,
    ImageOrigin,
    PictureSlot,
    PictureTarget,
    TermsVersion,
)
from .image_intake import ACCEPTED_TYPES, IMAGE_BYTES_MAX

__all__ = [
    "EXPIRED",
    "LINK_PARAM",
    "LINK_PREFIX",
    "LINK_STATES",
    "OPEN",
    "OPEN_LINKS_MAX",
    "SLOT_PREFIX",
    "SLOT_UPLOAD_ROUTE",
    "UPLOAD_LINK_LIFETIME",
    "UPLOAD_LINK_SCHEMA_VERSION",
    "UPLOAD_PAGE_PATH",
    "UPLOAD_TYPES",
    "USED",
    "LinkState",
    "RenewedLink",
    "SlotCraft",
    "SlotDeclaration",
    "SlotFact",
    "SlotMaterial",
    "SlotStage",
    "UploadLinkView",
    "UploadSlot",
    "UploadStart",
    "declared",
    "link_state",
    "slot_upload_url",
    "upload_page_url",
]

UPLOAD_LINK_SCHEMA_VERSION = 1
UPLOAD_LINK_LIFETIME = timedelta(minutes=30)
OPEN_LINKS_MAX = 10
LINK_PREFIX = "kvup_pg_"
SLOT_PREFIX = "kvup_sl_"
UPLOAD_PAGE_PATH = "/contributions/pictures/upload"
LINK_PARAM = "link"
SLOT_UPLOAD_ROUTE = "/api/upload-links/slots"
UPLOAD_TYPES = ACCEPTED_TYPES
OPEN = "OPEN"
USED = "USED"
EXPIRED = "EXPIRED"
LINK_STATES = (OPEN, USED, EXPIRED)
EACH_FACT_ONCE = "Each fact is named once"

LinkState = Literal[*LINK_STATES]


class UploadSlot(PictureTarget):
    craft_slug: str = Field(min_length=1, max_length=SLUG_MAX_CHARS)
    claim_ids: list[uuid.UUID] = Field(min_length=1, max_length=CLAIMS_MAX)

    @model_validator(mode="after")
    def _each_fact_once(self) -> Self:
        if len(set(self.claim_ids)) != len(self.claim_ids):
            raise ValueError(EACH_FACT_ONCE)
        return self


class SlotDeclaration(ContractModel):
    origin: ImageOrigin
    generator: str | None = Field(default=None, min_length=2, max_length=GENERATOR_MAX_CHARS)
    prompt: str | None = Field(default=None, min_length=1, max_length=PROMPT_MAX_CHARS)
    caption: str = Field(min_length=3, max_length=IMAGE_TEXT_MAX_CHARS)
    alt_text: str = Field(min_length=3, max_length=IMAGE_TEXT_MAX_CHARS)
    rights_confirmed: Literal[True]
    terms_version: TermsVersion


class SlotCraft(ContractModel):
    slug: str
    name: str


class SlotStage(ContractModel):
    id: uuid.UUID
    name: str


class SlotMaterial(ContractModel):
    id: uuid.UUID
    name: str


class SlotFact(ContractModel):
    id: uuid.UUID
    text: str


class UploadStart(ContractModel):
    schema_version: Literal[1] = UPLOAD_LINK_SCHEMA_VERSION
    link: str
    expires_at: datetime
    upload_url: str | None
    upload_method: Literal["PUT"] = "PUT"
    upload_types: list[str] = Field(default_factory=lambda: list(UPLOAD_TYPES))
    upload_max_bytes: int = IMAGE_BYTES_MAX
    craft: SlotCraft
    stage: SlotStage | None
    material: SlotMaterial | None = None
    slot: PictureSlot | None = None
    task_key: str | None = None
    facts: list[SlotFact]
    declared: bool
    next_step: str


class UploadLinkView(ContractModel):
    state: LinkState
    craft: SlotCraft
    stage: SlotStage | None
    material: SlotMaterial | None
    slot: PictureSlot | None
    task_key: str | None
    facts: list[SlotFact]
    expires_at: datetime
    contribution_id: uuid.UUID | None


class RenewedLink(ContractModel):
    token: str
    link: str
    expires_at: datetime


def link_state(*, used_at: datetime | None, expires_at: datetime, now: datetime) -> LinkState:
    if used_at is not None:
        return USED
    if expires_at <= now:
        return EXPIRED
    return OPEN


def declared(slot: UploadSlot, declaration: SlotDeclaration) -> ImageDeclaration:
    return ImageDeclaration(**slot.model_dump(by_alias=False), **declaration.model_dump(by_alias=False))


def upload_page_url(site: str, token: str) -> str:
    return f"{site.rstrip('/')}{UPLOAD_PAGE_PATH}?{urlencode({LINK_PARAM: token})}"


def slot_upload_url(api_origin: str, token: str) -> str:
    return f"{api_origin.rstrip('/')}{SLOT_UPLOAD_ROUTE}/{quote(token, safe='')}"
