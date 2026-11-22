import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.public_deps import public_asset_reader
from app.core.db import get_session, release_connection
from app.core.errors import AppError
from app.core.http_cache import not_modified, revalidation_headers
from app.models import User
from app.research.image_intake_svg import SVG_POLICY
from app.services.answering import NOT_FOUND_DETAIL
from app.services.contributed_pictures import shown_picture
from app.services.drawing_themes import THEME_PATTERN, themed_picture
from app.services.object_store import media_bucket

router = APIRouter(prefix="/crafts", tags=["crafts"])
logger = logging.getLogger(__name__)

PICTURE_CACHE = "private, max-age=300"
NO_PICTURES = "Contributed pictures are not available right now."
NO_SNIFF = {"X-Content-Type-Options": "nosniff", "Content-Security-Policy": SVG_POLICY}


@router.get("/contributed/{contribution_id}")
async def get_contributed_picture(
    request: Request,
    contribution_id: uuid.UUID,
    theme: str | None = Query(default=None, pattern=THEME_PATTERN),
    reader: User | None = Depends(public_asset_reader),
    session: AsyncSession = Depends(get_session),
) -> Response:
    shown = await shown_picture(session, contribution_id)
    await release_connection(session)
    if shown is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND_DETAIL)
    unchanged = not_modified(request, shown.sha256, cache_control=PICTURE_CACHE)
    if unchanged is not None:
        unchanged.headers.update(NO_SNIFF)
        return unchanged
    bucket = media_bucket()
    if bucket is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, NO_PICTURES)
    try:
        data = await bucket.get(shown.key)
    except AppError as error:
        logger.warning("contributed picture %s could not be read: %s", contribution_id, error)
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, NO_PICTURES) from None
    if data is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND_DETAIL)
    headers = {**revalidation_headers(shown.sha256, cache_control=PICTURE_CACHE), **NO_SNIFF}
    return Response(themed_picture(data, shown.mime, theme), media_type=shown.mime, headers=headers)
