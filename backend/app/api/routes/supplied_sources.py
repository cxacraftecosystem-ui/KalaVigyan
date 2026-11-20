from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.multipart_form import BodyTooLarge, limited_body
from app.api.public_deps import counted_anonymous_read
from app.core.db import get_session
from app.core.deps import require
from app.core.errors import InvalidInput
from app.core.roles import Capability
from app.models import User
from app.research.supplied_sources import SuppliedSourceReply, SuppliedSourceView
from app.services import supplied_sources as supplied
from app.services.supplied_sources_pdf import FILE_BYTES_MAX
from app.services.supplied_sources_views import supplied_reply, supplied_view

router = APIRouter(prefix="/knowledge/supplied-sources", tags=["knowledge"])
contributor = require(Capability.PROPOSE_KNOWLEDGE)

SlotToken = Annotated[str, Path(min_length=1, max_length=200, pattern=r"^[A-Za-z0-9_-]+$")]
NOT_FOUND = "No upload slot has that address."
NO_SOURCE = "No supplied source of yours has that id."
TOO_LARGE = f"A supplied file is at most {FILE_BYTES_MAX // (1024 * 1024)} MB."
PRIVATE = {"Cache-Control": "private, no-store", "X-Robots-Tag": "noindex, nofollow"}


@router.put("/slots/{token}")
async def fill_supplied_slot(
    token: SlotToken, request: Request, session: AsyncSession = Depends(get_session)
) -> SuppliedSourceReply:
    await counted_anonymous_read(request)
    data = await _body(request)
    try:
        row = await supplied.fill_supplied_slot(session, token, data, now=datetime.now(UTC))
    except supplied.UnknownSlot as missing:
        await session.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, NOT_FOUND) from missing
    except supplied.SuppliedGone as gone:
        await session.rollback()
        raise HTTPException(status.HTTP_410_GONE, gone.detail) from gone
    except InvalidInput as invalid:
        await session.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(invalid)) from invalid
    await session.commit()
    return supplied_reply(row)


@router.get("/{supplied_id}")
async def get_supplied_source(
    supplied_id: uuid.UUID,
    response: Response,
    user: User = Depends(contributor),
    session: AsyncSession = Depends(get_session),
) -> SuppliedSourceView:
    response.headers.update(PRIVATE)
    try:
        row = await supplied.own_supplied(session, user, supplied_id)
    except InvalidInput as missing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NO_SOURCE) from missing
    return supplied_view(row)


async def _body(request: Request) -> bytes:
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > FILE_BYTES_MAX:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, TOO_LARGE)
    try:
        return await limited_body(request, FILE_BYTES_MAX)
    except BodyTooLarge as too_large:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, TOO_LARGE) from too_large
