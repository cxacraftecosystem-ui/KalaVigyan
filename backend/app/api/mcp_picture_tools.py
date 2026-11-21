from __future__ import annotations

from datetime import UTC, datetime

from app.core.errors import ExternalFailure, InvalidInput
from app.core.mcp_scopes import CONTRIBUTE_SCOPE
from app.core.rate_limit import IMAGE_UPLOADS
from app.models import User
from app.providers.picture_vision import picture_screen_tools
from app.research.image_contributions_give import GivenPictures
from app.research.image_intake_fetch import PictureFetcher, decoded_base64
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

from .mcp_picture_arguments import (
    GivenOrUploaded,
    GivePictures,
    PicturesReply,
    UploadPlace,
    slot_declaration,
    upload_slot,
)
from .mcp_picture_texts import GIVE_DESCRIPTION, LINK_STEP, SHELL_STEP
from .mcp_tool_base import OPEN_WRITES, PICTURES, Tool, ToolContext, signed_in
from .oauth_hosts import endpoints_or_none
from .proposal_limits import refuse_tool_when_spent, spent_limit

__all__ = ["GIVE_PICTURES", "PICTURE_TOOLS", "start_picture"]

NO_BUCKET = "Pictures cannot be stored right now."
UNFETCHED = "The picture's link could not be fetched right now; try again or send its bytes."
NOTHING = "No picture was given and no upload was started: read each one's refusal, fix it and call again."


async def start_picture(
    context: ToolContext, slot: UploadSlot, declaration: SlotDeclaration | None
) -> UploadStart:
    user = signed_in(context)
    await refuse_tool_when_spent(IMAGE_UPLOADS, user)
    issued = await upload_links.start_upload(context.session, user, slot, declaration, now=datetime.now(UTC))
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
        declared=declaration is not None,
        next_step=LINK_STEP if upload_url is None else SHELL_STEP,
    )


async def _uploaded(
    context: ToolContext, arguments: GivePictures, position: int, picture: GivenOrUploaded
) -> UploadPlace:
    try:
        slot = upload_slot(arguments.craft_slug, picture)
        started = await start_picture(context, slot, slot_declaration(arguments.declaration, picture))
    except InvalidInput as refused:
        return UploadPlace(position=position, refused=str(refused))
    return UploadPlace(position=position, upload=started)


async def _given(context: ToolContext, user: User, arguments: GivePictures) -> GivenPictures:
    objects = media_bucket()
    if objects is None:
        raise InvalidInput(NO_BUCKET)
    shared, words = arguments.declaration, arguments.confirmation
    if shared is None or words is None:
        raise InvalidInput(NOTHING)
    async with picture_fetcher() as fetcher:
        files = [await _file(at, picture, fetcher, user) for at, picture in arguments.placed(False)]
    giving = Giving(craft_slug=arguments.craft_slug, shared=shared, confirmation=words, files=files)
    handing = Handing(objects=objects, tools=picture_screen_tools(), now=datetime.now(UTC))
    return await give_pictures(context.session, user, giving, handing=handing)


async def _file(position: int, picture: GivenOrUploaded, fetcher: PictureFetcher, user: User) -> GivenFile:
    batch = picture.batch_picture()
    spent = await spent_limit(IMAGE_UPLOADS, user)
    if spent is not None:
        return GivenFile(position, batch, None, spent.message)
    try:
        if picture.image_base64 is not None:
            data = decoded_base64(picture.image_base64)
        else:
            data = (await fetcher.fetch_picture(str(picture.image_url))).data
    except InvalidInput as refused:
        return GivenFile(position, batch, None, str(refused))
    except ExternalFailure:
        return GivenFile(position, batch, None, UNFETCHED)
    return GivenFile(position, batch, data)


async def _give_pictures(context: ToolContext, arguments: GivePictures) -> PicturesReply:
    user = signed_in(context)
    given = await _given(context, user, arguments) if arguments.placed(False) else None
    uploads = [await _uploaded(context, arguments, at, picture) for at, picture in arguments.placed(True)]
    started = [place.upload for place in uploads if place.upload is not None]
    steps = [given.next_step] if given is not None else []
    steps += [started[0].next_step] if started else []
    craft = given.craft if given is not None else (started[0].craft if started else None)
    return PicturesReply(
        craft=craft,
        declaration_id=None if given is None else given.declaration_id,
        given=0 if given is None else given.given,
        refused=(0 if given is None else given.refused) + len(uploads) - len(started),
        pictures=[] if given is None else given.pictures,
        uploads=uploads,
        next_step=" ".join(steps) or NOTHING,
    )


GIVE_PICTURES = Tool(
    "give_pictures",
    "Give pictures of a craft",
    GIVE_DESCRIPTION,
    GivePictures,
    PicturesReply,
    _give_pictures,
    CONTRIBUTE_SCOPE,
    OPEN_WRITES,
    group=PICTURES,
)
PICTURE_TOOLS: tuple[Tool, ...] = (GIVE_PICTURES,)
