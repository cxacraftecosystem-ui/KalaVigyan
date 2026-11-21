import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.public_deps import cached_read, public_asset_reader, public_reader
from app.core.db import get_session
from app.core.errors import InvalidInput, NotConfigured
from app.models import User
from app.research.field_voices import FIELD_LIST_KINDS
from app.services import knowledge_view
from app.services.answering import NOT_FOUND_DETAIL
from app.services.field_photo_scope import served_photo
from app.services.field_voices_reading import field_list, field_transcript
from app.services.naming import content_disposition
from app.services.object_store import media_bucket

router = APIRouter(tags=["field-voices"])

IMAGE_LINK_SECONDS = 900
UNKNOWN_CURSOR = "Unknown cursor."
NO_IMAGES = "Field photographs are not available right now."

ListKind = Literal[*FIELD_LIST_KINDS]


@router.get("/crafts/{slug}/field-voices")
async def get_craft_field_voices(
    slug: str,
    request: Request,
    response: Response,
    kind: ListKind = "quotes",
    cursor: str | None = None,
    *,
    reader: User | None = Depends(public_reader),
    session: AsyncSession = Depends(get_session),
) -> Any:
    craft = await knowledge_view.resolve_craft(session, slug)
    if craft is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND_DETAIL)
    try:
        listed = await field_list(session, craft, kind=kind, cursor=cursor)
    except InvalidInput:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, UNKNOWN_CURSOR) from None
    return cached_read(request, response, reader, listed.model_dump(mode="json", by_alias=True))


@router.get("/field-voices/recordings/{recording_id}")
async def get_field_recording(
    recording_id: uuid.UUID,
    request: Request,
    response: Response,
    reader: User | None = Depends(public_reader),
    session: AsyncSession = Depends(get_session),
) -> Any:
    transcript = await field_transcript(session, recording_id)
    if transcript is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND_DETAIL)
    return cached_read(request, response, reader, transcript.model_dump(mode="json", by_alias=True))


@router.get("/field-voices/images/{image_id}")
async def get_field_image(
    image_id: uuid.UUID,
    reader: User | None = Depends(public_asset_reader),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    served = await served_photo(session, image_id)
    if served is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND_DETAIL)
    bucket = media_bucket()
    if bucket is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, NO_IMAGES)
    leaf = served.key.rsplit("/", 1)[-1]
    try:
        link = bucket.presigned_get(
            served.key,
            disposition=content_disposition(leaf, inline=True),
            seconds=IMAGE_LINK_SECONDS,
            now=datetime.now(UTC),
        )
    except NotConfigured:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, NO_IMAGES) from None
    return RedirectResponse(
        link.url, status.HTTP_302_FOUND, headers={"Cache-Control": "private, max-age=300"}
    )
