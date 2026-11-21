from __future__ import annotations

from collections.abc import Awaitable
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.multipart_form import BodyTooLarge, form_file, limited_body
from app.api.public_deps import counted_anonymous_read
from app.core.config import get_settings
from app.core.db import get_session
from app.core.deps import require
from app.core.errors import InvalidInput
from app.core.http_cache import PRIVATE_NO_CACHE
from app.core.roles import Capability
from app.models import ImageContribution, User
from app.providers.picture_vision import picture_screen_tools
from app.research.image_contributions import ImageContributionView
from app.research.image_intake import IMAGE_BYTES_MAX
from app.research.upload_links import RenewedLink, SlotDeclaration, UploadLinkView, upload_page_url
from app.services import image_contributions as images, upload_links as links
from app.services.object_store import ObjectStore, media_bucket

router = APIRouter(prefix="/upload-links", tags=["contributions"])
contributor = require(Capability.PROPOSE_KNOWLEDGE)

LinkToken = Annotated[str, Path(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_-]+$")]
DECLARATION_FIELD = "declaration"
PICTURE_FIELD = "picture"
FORM_OVERHEAD_BYTES = 64 * 1024
NOT_FOUND_DETAIL = "No upload link of yours has that address."
TOO_LARGE_DETAIL = f"A contributed picture is at most {IMAGE_BYTES_MAX // (1024 * 1024)} MB."
NO_BUCKET_DETAIL = "Pictures cannot be stored right now."
UNREADABLE_DECLARATION = "The declaration is not a valid picture declaration."


@router.get("/{token}")
async def get_upload_link(
    token: LinkToken,
    response: Response,
    user: User = Depends(contributor),
    session: AsyncSession = Depends(get_session),
) -> UploadLinkView:
    response.headers["Cache-Control"] = PRIVATE_NO_CACHE
    return await _refusals(session, links.link_view(session, user, token, now=_now()))


@router.post("/{token}/picture", status_code=status.HTTP_201_CREATED)
async def give_picture(
    token: LinkToken,
    request: Request,
    user: User = Depends(contributor),
    session: AsyncSession = Depends(get_session),
) -> ImageContributionView:
    objects = _bucket()
    picture = await _form_picture(request)
    filled = links.fill_by_link(session, user, token, picture, filling=_filling(objects))
    return await _shown(session, await _refusals(session, filled), objects)


@router.post("/{token}/renew", status_code=status.HTTP_201_CREATED)
async def renew_upload_link(
    token: LinkToken,
    user: User = Depends(contributor),
    session: AsyncSession = Depends(get_session),
) -> RenewedLink:
    issued = await _refusals(session, links.renew_link(session, user, token, now=_now()))
    await session.commit()
    site = get_settings().public_web_url
    return RenewedLink(
        token=issued.link_token,
        link=upload_page_url(site, issued.link_token),
        expires_at=issued.expires_at,
    )


@router.put("/slots/{token}")
async def fill_upload_slot(
    token: LinkToken, request: Request, session: AsyncSession = Depends(get_session)
) -> ImageContributionView:
    await counted_anonymous_read(request)
    objects = _bucket()
    data = await _body(request, IMAGE_BYTES_MAX)
    filled = links.fill_slot(session, token, data, filling=_filling(objects))
    return await _shown(session, await _refusals(session, filled), objects)


async def _refusals[Done](session: AsyncSession, step: Awaitable[Done]) -> Done:
    try:
        return await step
    except links.UnknownLink as missing:
        await session.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND_DETAIL) from missing
    except links.LinkGone as gone:
        await session.rollback()
        raise HTTPException(status.HTTP_410_GONE, gone.detail) from gone
    except (links.LinkRefused, images.ContributionRefused) as refused:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, refused.detail) from refused
    except images.UnknownImage as missing:
        await session.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND_DETAIL) from missing
    except InvalidInput as invalid:
        await session.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(invalid)) from invalid


async def _shown(
    session: AsyncSession, row: ImageContribution, objects: ObjectStore
) -> ImageContributionView:
    await session.commit()
    return (await images.views(session, [row], objects=objects, now=_now()))[0]


async def _form_picture(request: Request) -> links.Picture:
    body = await _body(request, IMAGE_BYTES_MAX + FORM_OVERHEAD_BYTES)
    content_type = request.headers.get("content-type")
    try:
        declaration = form_file(content_type, body, DECLARATION_FIELD)
        picture = form_file(content_type, body, PICTURE_FIELD)
        parsed = SlotDeclaration.model_validate_json(declaration.content)
    except InvalidInput as invalid:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(invalid)) from invalid
    except ValidationError as refused:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, UNREADABLE_DECLARATION) from refused
    if len(picture.content) > IMAGE_BYTES_MAX:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, TOO_LARGE_DETAIL)
    return links.Picture(declaration=parsed, data=picture.content)


async def _body(request: Request, limit: int) -> bytes:
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > limit:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, TOO_LARGE_DETAIL)
    try:
        return await limited_body(request, limit)
    except BodyTooLarge as too_large:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, TOO_LARGE_DETAIL) from too_large


def _filling(objects: ObjectStore) -> links.Filling:
    return links.Filling(objects=objects, tools=picture_screen_tools(), now=_now())


def _bucket() -> ObjectStore:
    objects = media_bucket()
    if objects is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, NO_BUCKET_DETAIL)
    return objects


def _now() -> datetime:
    return datetime.now(UTC)
