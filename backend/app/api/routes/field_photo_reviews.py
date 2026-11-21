import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session, session_scope
from app.core.deps import require
from app.core.errors import InvalidInput
from app.core.http_cache import PRIVATE_NO_CACHE
from app.core.roles import Capability
from app.models import User
from app.providers.picture_vision import picture_screen_tools
from app.research.field_photo_reviews import QUEUE_STATES, PhotoDecisionRequest
from app.services.field_photo_crops import PhotoRefused, release_crop
from app.services.field_photo_decisions import Decided, UnknownPhoto, decide_photo, refresh_photo_pages
from app.services.field_photo_queue import photo_item_of, photo_queue
from app.services.field_photo_screens import SCREENS_PER_CALL, screen_held_photos
from app.services.object_store import media_bucket

router = APIRouter(prefix="/field-photos", tags=["field-voices"])
reviewer = require(Capability.REVIEW_CONTRIBUTIONS)

UNKNOWN_CURSOR = "Unknown cursor."
NOT_FOUND = "No field photograph has that id."
NO_PHOTOS = "Field photographs cannot be read right now. Try again later."

QueueState = Literal[*QUEUE_STATES]


@router.get("/review")
async def get_photo_queue(
    response: Response,
    state: QueueState = "WAITING",
    cursor: str | None = None,
    *,
    _: User = Depends(reviewer),
    session: AsyncSession = Depends(get_session),
) -> Any:
    try:
        queue = await photo_queue(session, state=state, cursor=cursor, objects=media_bucket(), now=_now())
    except InvalidInput:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, UNKNOWN_CURSOR) from None
    response.headers["Cache-Control"] = PRIVATE_NO_CACHE
    return queue.model_dump(mode="json", by_alias=True)


@router.post("/{image_id}/decision")
async def post_photo_decision(
    image_id: uuid.UUID,
    body: PhotoDecisionRequest,
    response: Response,
    actor: User = Depends(reviewer),
    session: AsyncSession = Depends(get_session),
) -> Any:
    objects = media_bucket()
    decided = await _decided(session, image_id, body, actor)
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        await release_crop(session, objects, decided.made_key)
        raise
    await release_crop(session, objects, decided.released_key)
    await refresh_photo_pages(session, image_id)
    item = await photo_item_of(session, image_id, objects=objects, now=_now())
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND)
    response.headers["Cache-Control"] = PRIVATE_NO_CACHE
    return item.model_dump(mode="json", by_alias=True)


@router.post("/screen")
async def post_photo_screens(actor: User = Depends(reviewer)) -> Any:
    objects = media_bucket()
    if objects is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, NO_PHOTOS)
    report = await screen_held_photos(
        session_scope, objects, picture_screen_tools(), limit=SCREENS_PER_CALL, actor=actor
    )
    return report.as_dict()


async def _decided(
    session: AsyncSession, image_id: uuid.UUID, body: PhotoDecisionRequest, actor: User
) -> Decided:
    try:
        return await decide_photo(session, image_id, body, actor=actor, objects=media_bucket())
    except UnknownPhoto:
        await session.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND) from None
    except PhotoRefused as refused:
        await session.rollback()
        raise HTTPException(refused.status, refused.detail) from None


def _now() -> datetime:
    return datetime.now(UTC)
