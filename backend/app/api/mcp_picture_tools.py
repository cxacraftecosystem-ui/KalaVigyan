from __future__ import annotations

import uuid
from datetime import UTC, datetime
from types import MappingProxyType
from typing import Self

from pydantic import Field, ValidationError, model_validator

from app.core.errors import ExternalFailure, InvalidInput
from app.core.mcp_scopes import CONTRIBUTE_SCOPE
from app.core.rate_limit import IMAGE_UPLOADS
from app.models import User
from app.models.open_work import TASK_KEY_COLUMN_CHARS
from app.research.base import HttpsUrl
from app.research.crafts import SLUG_MAX_CHARS
from app.research.image_contributions import (
    BATCH_PICTURES_MAX,
    CLAIMS_MAX,
    BatchPicture,
    PictureSlot,
    SharedDeclaration,
)
from app.research.image_contributions_give import (
    CONFIRMATION_MAX_CHARS,
    GIVEN_BASE64_BYTES_MAX,
    GivenItem,
    GivenPictures,
    source_problem,
)
from app.research.image_intake_fetch import (
    IMAGE_BASE64_BYTES_MAX,
    PictureFetcher,
    base64_chars_max,
    decoded_base64,
)
from app.research.upload_links import (
    SlotDeclaration,
    UploadSlot,
    UploadStart,
    slot_upload_url,
    upload_page_url,
)
from app.services import upload_links
from app.services.object_store import media_bucket
from app.services.upload_links_fetch import picture_fetcher
from app.services.upload_links_give import GivenFile, Giving, Handing, give_pictures

from .mcp_picture_texts import (
    CONFIRMATION_FIELD,
    DECLARATION_FIELD,
    GIVE_DESCRIPTION,
    GIVES_DESCRIPTION,
    LINK_STEP,
    SHARED_DECLARATION_FIELD,
    SHELL_STEP,
    START_DESCRIPTION,
)
from .mcp_tool_base import WRITES, Arguments, Tool, ToolContext
from .oauth_hosts import endpoints_or_none
from .picture_vision import picture_screen_tools
from .proposal_limits import refuse_tool_when_spent, spent_limit

__all__ = [
    "GIVE_IMAGE",
    "GIVE_IMAGES",
    "PICTURE_TOOLS",
    "SIGN_IN",
    "START_IMAGE_UPLOAD",
    "GiveImage",
    "GiveImages",
    "StartImageUpload",
    "signed_in",
]

SIGN_IN = "This tool needs a signed-in connection."
NO_BUCKET = "Pictures cannot be stored right now."
UNFETCHED = "The picture's link could not be fetched right now; try again or send its bytes."
TOO_MUCH_BASE64 = (
    f"The pictures sent in one call are at most {GIVEN_BASE64_BYTES_MAX // (1024 * 1024)} MB together"
)
OPEN_WRITES = MappingProxyType({"readOnlyHint": False, "destructiveHint": False, "openWorldHint": True})


class Targeted(Arguments):
    craft_slug: str = Field(min_length=1, max_length=SLUG_MAX_CHARS, description="A slug from find_crafts")
    stage_id: uuid.UUID | None = Field(
        default=None, description="One of the craft's stages, when it shows one"
    )
    material_id: uuid.UUID | None = Field(
        default=None, description="One of the craft's materials, when it shows one"
    )
    slot: PictureSlot | None = Field(
        default=None, description="MASTHEAD for the page's first picture, RECORD for the GI record's picture"
    )
    task_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=TASK_KEY_COLUMN_CHARS,
        description="A MISSING_PICTURE task from list_open_work; its stage, material or slot is used when none is given",
    )


class StartImageUpload(Targeted):
    claim_ids: list[uuid.UUID] = Field(
        min_length=1,
        max_length=CLAIMS_MAX,
        description="The ids of the facts the picture shows, from get_facts",
    )
    declaration: SlotDeclaration | None = Field(default=None, description=DECLARATION_FIELD)


class GiveImage(Targeted):
    image_url: HttpsUrl | None = Field(
        default=None,
        description="An https link to the picture itself, at most 10 MB; KalaVigyan's server fetches it",
    )
    image_base64: str | None = Field(
        default=None,
        min_length=8,
        max_length=base64_chars_max(IMAGE_BASE64_BYTES_MAX) + 64,
        description="The picture's bytes in base64, or a data: URI, at most 6 MB before encoding",
    )
    claim_ids: list[uuid.UUID] = Field(
        default_factory=list,
        max_length=CLAIMS_MAX,
        description="The facts the picture shows; an AI image names one",
    )
    declaration: SlotDeclaration = Field(description=DECLARATION_FIELD)
    confirmation: str = Field(min_length=2, max_length=CONFIRMATION_MAX_CHARS, description=CONFIRMATION_FIELD)

    @model_validator(mode="after")
    def _one_source(self) -> Self:
        problem = source_problem(self.image_url, self.image_base64)
        if problem:
            raise ValueError(problem)
        return self


class GiveImages(Arguments):
    craft_slug: str = Field(min_length=1, max_length=SLUG_MAX_CHARS, description="A slug from find_crafts")
    declaration: SharedDeclaration = Field(description=SHARED_DECLARATION_FIELD)
    confirmation: str = Field(min_length=2, max_length=CONFIRMATION_MAX_CHARS, description=CONFIRMATION_FIELD)
    pictures: list[GivenItem] = Field(min_length=1, max_length=BATCH_PICTURES_MAX)

    @model_validator(mode="after")
    def _base64_fits(self) -> Self:
        sent = sum(len(picture.image_base64 or "") for picture in self.pictures)
        if sent > base64_chars_max(GIVEN_BASE64_BYTES_MAX):
            raise ValueError(TOO_MUCH_BASE64)
        return self


def signed_in(context: ToolContext) -> User:
    if context.user is None:
        raise InvalidInput(SIGN_IN)
    return context.user


async def _start_image_upload(context: ToolContext, arguments: StartImageUpload) -> UploadStart:
    user = signed_in(context)
    slot = _slot(arguments)
    refuse_tool_when_spent(IMAGE_UPLOADS, user)
    issued = await upload_links.start_upload(
        context.session, user, slot, arguments.declaration, now=datetime.now(UTC)
    )
    endpoints = endpoints_or_none()
    upload_url = (
        None
        if issued.slot_token is None or endpoints is None
        else slot_upload_url(endpoints.issuer, issued.slot_token)
    )
    return UploadStart(
        link=upload_page_url(context.site, issued.link_token),
        expires_at=issued.expires_at,
        upload_url=upload_url,
        craft=issued.craft,
        stage=issued.stage,
        material=issued.material,
        slot=issued.slot,
        task_key=issued.task_key,
        facts=issued.facts,
        declared=arguments.declaration is not None,
        next_step=LINK_STEP if upload_url is None else SHELL_STEP,
    )


def _slot(arguments: StartImageUpload) -> UploadSlot:
    try:
        return UploadSlot.model_validate(arguments.model_dump(exclude={"declaration"}))
    except ValidationError as refused:
        raise InvalidInput("; ".join(str(problem["msg"]) for problem in refused.errors())) from None


async def _give_image(context: ToolContext, arguments: GiveImage) -> GivenPictures:
    declared = arguments.declaration
    shared = SharedDeclaration(
        origin=declared.origin,
        generator=declared.generator,
        rights_confirmed=declared.rights_confirmed,
        terms_version=declared.terms_version,
    )
    try:
        picture = GivenItem(
            **arguments.model_dump(include={"stage_id", "material_id", "slot", "task_key", "claim_ids"}),
            **arguments.model_dump(include={"image_url", "image_base64"}),
            prompt=declared.prompt,
            caption=declared.caption,
            alt_text=declared.alt_text,
        )
    except ValidationError as refused:
        raise InvalidInput("; ".join(str(problem["msg"]) for problem in refused.errors())) from None
    return await _given(context, arguments.craft_slug, shared, arguments.confirmation, [picture])


async def _give_images(context: ToolContext, arguments: GiveImages) -> GivenPictures:
    return await _given(
        context, arguments.craft_slug, arguments.declaration, arguments.confirmation, list(arguments.pictures)
    )


async def _given(
    context: ToolContext,
    craft_slug: str,
    shared: SharedDeclaration,
    confirmation: str,
    items: list[GivenItem],
) -> GivenPictures:
    user = signed_in(context)
    objects = media_bucket()
    if objects is None:
        raise InvalidInput(NO_BUCKET)
    async with picture_fetcher() as fetcher:
        files = [await _file(position, item, fetcher, user) for position, item in enumerate(items, start=1)]
    giving = Giving(craft_slug=craft_slug, shared=shared, confirmation=confirmation, files=files)
    handing = Handing(objects=objects, tools=picture_screen_tools(), now=datetime.now(UTC))
    return await give_pictures(context.session, user, giving, handing=handing)


async def _file(position: int, item: GivenItem, fetcher: PictureFetcher, user: User) -> GivenFile:
    picture = BatchPicture.model_validate(item.model_dump(exclude={"image_url", "image_base64"}))
    spent = spent_limit(IMAGE_UPLOADS, user)
    if spent is not None:
        return GivenFile(position, picture, None, spent.message)
    try:
        if item.image_base64 is not None:
            data = decoded_base64(item.image_base64)
        else:
            data = (await fetcher.fetch_picture(str(item.image_url))).data
    except InvalidInput as refused:
        return GivenFile(position, picture, None, str(refused))
    except ExternalFailure:
        return GivenFile(position, picture, None, UNFETCHED)
    return GivenFile(position, picture, data)


START_IMAGE_UPLOAD = Tool(
    "start_image_upload",
    "Start giving a picture",
    START_DESCRIPTION,
    StartImageUpload,
    UploadStart,
    _start_image_upload,
    CONTRIBUTE_SCOPE,
    WRITES,
)
GIVE_IMAGE = Tool(
    "give_image",
    "Give a picture from the chat",
    GIVE_DESCRIPTION,
    GiveImage,
    GivenPictures,
    _give_image,
    CONTRIBUTE_SCOPE,
    OPEN_WRITES,
)
GIVE_IMAGES = Tool(
    "give_images",
    "Give several pictures of one craft",
    GIVES_DESCRIPTION,
    GiveImages,
    GivenPictures,
    _give_images,
    CONTRIBUTE_SCOPE,
    OPEN_WRITES,
)
PICTURE_TOOLS: tuple[Tool, ...] = (GIVE_IMAGE, GIVE_IMAGES)
