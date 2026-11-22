from __future__ import annotations

import uuid
from collections.abc import Awaitable
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.proposal_limits import proposal_limit
from app.core.db import get_session
from app.core.deps import require
from app.core.errors import InvalidInput
from app.core.rate_limit import IMAGE_UPLOADS
from app.core.roles import Capability
from app.models import ImageContribution, User
from app.providers.picture_vision import picture_screen_tools
from app.research.image_contributions import (
    ImageBatch,
    ImageContributionStatus,
    ImageContributionView,
    ImageDeclaration,
    ImageQueue,
)
from app.research.image_intake import IMAGE_BYTES_MAX
from app.services import image_contributions as images
from app.services.object_store import ObjectStore, media_bucket

router = APIRouter(prefix="/contributions/images", tags=["contributions"])
contributor = require(Capability.PROPOSE_KNOWLEDGE)
reviewer = require(Capability.REVIEW_CONTRIBUTIONS)

NOT_FOUND_DETAIL = "No contribution of yours has that id."
TOO_LARGE_DETAIL = f"A contributed picture is at most {IMAGE_BYTES_MAX // (1024 * 1024)} MB."
NO_BUCKET_DETAIL = "Pictures cannot be stored right now."
WEB = "WEB"


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(proposal_limit(IMAGE_UPLOADS, contributor))],
)
async def declare_image(
    body: ImageDeclaration, user: User = Depends(contributor), session: AsyncSession = Depends(get_session)
) -> ImageContributionView:
    return await _answer(session, images.declare(session, user, body, now=_now()))


@router.post(
    "/batch",
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(proposal_limit(IMAGE_UPLOADS, contributor))],
)
async def declare_images(
    body: ImageBatch, user: User = Depends(contributor), session: AsyncSession = Depends(get_session)
) -> list[ImageContributionView]:
    try:
        rows = await images.declare_batch(session, user, body, images.Filing(channel=WEB), now=_now())
    except InvalidInput as invalid:
        await session.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(invalid)) from invalid
    await session.commit()
    return await images.views(session, rows, objects=media_bucket(), now=_now())


@router.put("/{contribution_id}/file")
async def upload_image(
    contribution_id: uuid.UUID,
    request: Request,
    user: User = Depends(contributor),
    session: AsyncSession = Depends(get_session),
) -> ImageContributionView:
    objects = media_bucket()
    if objects is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, NO_BUCKET_DETAIL)
    upload = images.Upload(contribution_id=contribution_id, user=user, data=await _picture(request))
    received = images.receive_file(session, upload, objects=objects, tools=picture_screen_tools(), now=_now())
    return await _answer(session, received)


@router.get("/mine")
async def my_images(
    user: User = Depends(contributor), session: AsyncSession = Depends(get_session)
) -> list[ImageContributionView]:
    return await images.views(
        session, await images.own_images(session, user), objects=media_bucket(), now=_now()
    )


@router.post("/{contribution_id}/withdraw")
async def withdraw_image(
    contribution_id: uuid.UUID,
    user: User = Depends(contributor),
    session: AsyncSession = Depends(get_session),
) -> ImageContributionView:
    return await _answer(session, images.withdraw(session, contribution_id, user))


@router.get("/review")
async def review_queue(
    state: ImageContributionStatus = "PENDING",
    _: User = Depends(reviewer),
    session: AsyncSession = Depends(get_session),
) -> ImageQueue:
    rows = await images.queue(session, state)
    return ImageQueue(
        status=state, items=await images.views(session, rows, objects=media_bucket(), now=_now())
    )


def _now() -> datetime:
    return datetime.now(UTC)


async def _answer(session: AsyncSession, change: Awaitable[ImageContribution]) -> ImageContributionView:
    try:
        row = await change
    except images.UnknownImage as missing:
        await session.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND_DETAIL) from missing
    except images.ContributionRefused as refused:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, refused.detail) from refused
    except InvalidInput as invalid:
        await session.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(invalid)) from invalid
    await session.commit()
    objects: ObjectStore | None = media_bucket()
    return (await images.views(session, [row], objects=objects, now=_now()))[0]


async def _picture(request: Request) -> bytes:
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > IMAGE_BYTES_MAX:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, TOO_LARGE_DETAIL)
    received: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > IMAGE_BYTES_MAX:
            raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, TOO_LARGE_DETAIL)
        received.append(chunk)
    return b"".join(received)
