import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.public_deps import public_asset_reader
from app.core.db import get_session, release_connection
from app.core.errors import NotConfigured
from app.models import User
from app.services.answering import NOT_FOUND_DETAIL
from app.services.craft_ai_media import page_media_key_of
from app.services.naming import content_disposition
from app.services.object_store import media_bucket

router = APIRouter(prefix="/crafts", tags=["crafts"])

PAGE_MEDIA_LINK_SECONDS = 900
NO_MEDIA = "AI pictures and clips are not available right now."


@router.get("/media/{asset_id}")
async def get_page_media(
    asset_id: uuid.UUID,
    reader: User | None = Depends(public_asset_reader),
    session: AsyncSession = Depends(get_session),
) -> RedirectResponse:
    key = await page_media_key_of(session, asset_id)
    await release_connection(session)
    if key is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND_DETAIL)
    bucket = media_bucket()
    if bucket is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, NO_MEDIA)
    try:
        link = bucket.presigned_get(
            key,
            disposition=content_disposition(key.rsplit("/", 1)[-1], inline=True),
            seconds=PAGE_MEDIA_LINK_SECONDS,
            now=datetime.now(UTC),
        )
    except NotConfigured:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, NO_MEDIA) from None
    return RedirectResponse(
        link.url, status.HTTP_302_FOUND, headers={"Cache-Control": "private, max-age=300"}
    )
