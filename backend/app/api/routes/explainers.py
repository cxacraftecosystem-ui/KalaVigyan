from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Path, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import get_current_user
from app.core.http_cache import PRIVATE_NO_CACHE
from app.models import User
from app.research.explainer_versions import ExplainerVersionDocument
from app.services.explainer_history import (
    UNKNOWN_EXPLAINER_DETAIL,
    UnknownExplainer,
    explainer_history,
    explainer_version,
    latest_version,
    mark_seen,
)
from app.services.object_store import media_bucket
from app.services.share_links import (
    NOTHING_PUBLIC_DETAIL,
    NothingPublic,
    answer_share,
    share_answer,
    unshare_answer,
)

router = APIRouter(prefix="/explainers", tags=["explainers"])

VersionNumber = Annotated[int, Path(ge=1)]


@router.get("/{explainer_id}")
async def latest_explainer(
    explainer_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        document = await latest_version(session, explainer_id, user.id)
    except UnknownExplainer:
        raise HTTPException(status.HTTP_404_NOT_FOUND, UNKNOWN_EXPLAINER_DETAIL) from None
    return await _opened(session, user, document)


@router.get("/{explainer_id}/versions")
async def explainer_versions(
    explainer_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        history = await explainer_history(session, explainer_id, user.id)
    except UnknownExplainer:
        raise HTTPException(status.HTTP_404_NOT_FOUND, UNKNOWN_EXPLAINER_DETAIL) from None
    return history.model_dump(mode="json", by_alias=True)


@router.get("/{explainer_id}/versions/{version}")
async def explainer_at_version(
    explainer_id: uuid.UUID,
    version: int = Path(ge=1),
    *,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        document = await explainer_version(session, explainer_id, user.id, version)
    except UnknownExplainer:
        raise HTTPException(status.HTTP_404_NOT_FOUND, UNKNOWN_EXPLAINER_DETAIL) from None
    return await _opened(session, user, document)


@router.get("/{explainer_id}/versions/{version}/share")
async def get_explainer_share(
    explainer_id: uuid.UUID,
    version: VersionNumber,
    response: Response,
    *,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        link = await answer_share(session, user.id, explainer_id, version)
    except UnknownExplainer:
        raise HTTPException(status.HTTP_404_NOT_FOUND, UNKNOWN_EXPLAINER_DETAIL) from None
    response.headers["Cache-Control"] = PRIVATE_NO_CACHE
    return link.model_dump(mode="json", by_alias=True)


@router.put("/{explainer_id}/versions/{version}/share")
async def put_explainer_share(
    explainer_id: uuid.UUID,
    version: VersionNumber,
    response: Response,
    *,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        link = await share_answer(session, user.id, explainer_id, version, now=datetime.now(UTC))
    except UnknownExplainer:
        raise HTTPException(status.HTTP_404_NOT_FOUND, UNKNOWN_EXPLAINER_DETAIL) from None
    except NothingPublic:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, NOTHING_PUBLIC_DETAIL) from None
    response.headers["Cache-Control"] = PRIVATE_NO_CACHE
    return link.model_dump(mode="json", by_alias=True)


@router.delete("/{explainer_id}/versions/{version}/share", status_code=status.HTTP_204_NO_CONTENT)
async def delete_explainer_share(
    explainer_id: uuid.UUID,
    version: VersionNumber,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    if not await unshare_answer(session, user.id, explainer_id, version, objects=media_bucket()):
        raise HTTPException(status.HTTP_404_NOT_FOUND, UNKNOWN_EXPLAINER_DETAIL)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _opened(session: AsyncSession, user: User, document: ExplainerVersionDocument) -> dict[str, Any]:
    await mark_seen(session, user.id, document.mark.explainer_id, document.mark.version)
    await session.commit()
    return document.model_dump(mode="json", by_alias=True)
