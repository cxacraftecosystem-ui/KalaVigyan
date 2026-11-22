from __future__ import annotations

import uuid
from collections.abc import Awaitable
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.page_proposal_deps import page_proposed
from app.api.proposal_limits import proposal_limit
from app.api.structure_proposal_deps import site_origin
from app.core.db import get_session, release_connection
from app.core.deps import require
from app.core.errors import AppError, InvalidInput, Refused
from app.core.rate_limit import PAGE_PREVIEWS, PAGE_PROPOSALS
from app.core.roles import Capability
from app.models import User
from app.research.image_intake_svg import SVG_POLICY
from app.research.page_proposals import PageBundle, PagePreviewResult, PageProposalResult
from app.research.review_switch import CONTRIBUTION
from app.services.drawing_themes import THEME_PATTERN, themed_picture
from app.services.object_store import media_bucket
from app.services.own_proposals import require_terms
from app.services.page_preview import preview_page
from app.services.page_preview_links import UnknownPreview, preview_document
from app.services.page_preview_pictures import own_picture_file

router = APIRouter(prefix="/knowledge/pages", tags=["knowledge"])
proposer = require(Capability.PROPOSE_KNOWLEDGE)

PREVIEW_HEADERS = {"Cache-Control": "private, no-store", "X-Robots-Tag": "noindex, nofollow"}
PICTURE_HEADERS = {"X-Content-Type-Options": "nosniff", "Content-Security-Policy": SVG_POLICY}
TOKEN_PATTERN = r"^[0-9a-f]{32}\.\d{1,12}\.[0-9a-f]{64}$"
NO_PICTURE = "No picture of yours waiting or shown has that id."
PICTURE_UNREAD = "The picture could not be read just now. Try again in a minute."


@router.post("", dependencies=[Depends(proposal_limit(PAGE_PROPOSALS, proposer))])
async def propose_page_bundle(
    body: PageBundle, user: User = Depends(proposer), session: AsyncSession = Depends(get_session)
) -> PageProposalResult:
    await _terms(session, user)
    proposed = page_proposed(session, body, user, origin=CONTRIBUTION, site=site_origin())
    return await _written(session, proposed)


@router.post("/preview", dependencies=[Depends(proposal_limit(PAGE_PREVIEWS, proposer))])
async def preview_page_bundle(
    body: PageBundle, user: User = Depends(proposer), session: AsyncSession = Depends(get_session)
) -> PagePreviewResult:
    previewed = preview_page(session, user, body, site=site_origin(), now=datetime.now(UTC))
    return await _written(session, previewed)


@router.get("/previews/{token}")
async def read_preview(
    token: str = Path(pattern=TOKEN_PATTERN),
    user: User = Depends(proposer),
    session: AsyncSession = Depends(get_session),
) -> JSONResponse:
    try:
        document = await preview_document(session, user, token, now=datetime.now(UTC))
    except UnknownPreview as missing:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(missing), headers=PREVIEW_HEADERS) from None
    return JSONResponse(document, headers=PREVIEW_HEADERS)


@router.get("/pictures/{contribution_id}")
async def read_own_picture(
    contribution_id: uuid.UUID,
    theme: str | None = Query(default=None, pattern=THEME_PATTERN),
    user: User = Depends(proposer),
    session: AsyncSession = Depends(get_session),
) -> Response:
    found = await own_picture_file(session, user, contribution_id)
    await release_connection(session)
    bucket = media_bucket()
    if found is None or bucket is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NO_PICTURE, headers=PREVIEW_HEADERS)
    try:
        data = await bucket.get(found.key)
    except AppError:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, PICTURE_UNREAD) from None
    if data is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NO_PICTURE, headers=PREVIEW_HEADERS)
    themed = themed_picture(data, found.mime, theme)
    return Response(themed, media_type=found.mime, headers={**PREVIEW_HEADERS, **PICTURE_HEADERS})


async def _terms(session: AsyncSession, user: User) -> None:
    try:
        await require_terms(session, user)
    except Refused as refused:
        raise HTTPException(status.HTTP_403_FORBIDDEN, refused.message) from None


async def _written[Answer](session: AsyncSession, change: Awaitable[Answer]) -> Answer:
    try:
        answer = await change
    except InvalidInput as invalid:
        await session.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(invalid)) from None
    except Refused as refused:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, refused.message) from None
    await session.commit()
    return answer
