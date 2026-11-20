from __future__ import annotations

from collections.abc import Awaitable
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Path, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.page_proposal_deps import page_proposed
from app.api.structure_proposal_deps import site_origin
from app.core.db import get_session
from app.core.deps import require
from app.core.errors import InvalidInput, Refused
from app.core.roles import Capability
from app.models import User
from app.research.page_proposals import PageBundle, PagePreviewResult, PageProposalResult
from app.research.review_switch import CONTRIBUTION
from app.services.own_proposals import require_terms
from app.services.page_preview import preview_page
from app.services.page_preview_links import UnknownPreview, preview_document

router = APIRouter(prefix="/knowledge/pages", tags=["knowledge"])
proposer = require(Capability.PROPOSE_KNOWLEDGE)

PREVIEW_HEADERS = {"Cache-Control": "private, no-store", "X-Robots-Tag": "noindex, nofollow"}
TOKEN_PATTERN = r"^[0-9a-f]{32}\.\d{1,12}\.[0-9a-f]{64}$"


@router.post("")
async def propose_page_bundle(
    body: PageBundle, user: User = Depends(proposer), session: AsyncSession = Depends(get_session)
) -> PageProposalResult:
    await _terms(session, user)
    proposed = page_proposed(session, body, user, origin=CONTRIBUTION, site=site_origin())
    return await _written(session, proposed)


@router.post("/preview")
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
