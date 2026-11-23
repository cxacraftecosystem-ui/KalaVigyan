from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.export_deps import export_tools, lesson_file
from app.core.db import get_session
from app.core.deps import get_current_user, require
from app.core.http_cache import PRIVATE_NO_CACHE
from app.core.roles import Capability
from app.models import User
from app.research.lesson_builder import LessonNotBuildable, UnknownLessonSection
from app.research.lessons import LESSON_FORMATS, LessonRequest
from app.services.explainer_history import UNKNOWN_EXPLAINER_DETAIL, UnknownExplainer
from app.services.export_files import ExportTools
from app.services.lesson_packs import build_lesson, delete_lesson, lesson_list, lesson_of
from app.services.object_store import media_bucket
from app.services.share_links import (
    NOTHING_PUBLIC_DETAIL,
    NothingPublic,
    lesson_share,
    share_lesson,
    unshare_lesson,
)

router = APIRouter(prefix="/lessons", tags=["lessons"])

NO_LESSON_DETAIL = "No lesson has that address."

LessonFormat = Literal[*LESSON_FORMATS]


@router.post("", status_code=status.HTTP_201_CREATED)
async def post_lesson(
    request: LessonRequest,
    user: User = Depends(require(Capability.BUILD_LESSONS)),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        pack = await build_lesson(session, user.id, request, now=datetime.now(UTC))
    except UnknownExplainer, UnknownLessonSection:
        raise HTTPException(status.HTTP_404_NOT_FOUND, UNKNOWN_EXPLAINER_DETAIL) from None
    except LessonNotBuildable as refused:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, refused.detail) from None
    return pack.model_dump(mode="json", by_alias=True)


@router.get("")
async def get_lessons(
    response: Response,
    user: User = Depends(require(Capability.BUILD_LESSONS)),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    listed = await lesson_list(session, user.id)
    response.headers["Cache-Control"] = PRIVATE_NO_CACHE
    return listed.model_dump(mode="json", by_alias=True)


@router.get("/{lesson_id}")
async def get_lesson(
    lesson_id: uuid.UUID,
    response: Response,
    user: User = Depends(require(Capability.BUILD_LESSONS)),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    pack = await lesson_of(session, user.id, lesson_id)
    if pack is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NO_LESSON_DETAIL)
    response.headers["Cache-Control"] = PRIVATE_NO_CACHE
    return pack.model_dump(mode="json", by_alias=True)


@router.delete("/{lesson_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_lesson(
    lesson_id: uuid.UUID,
    user: User = Depends(require(Capability.BUILD_LESSONS)),
    session: AsyncSession = Depends(get_session),
) -> Response:
    if not await delete_lesson(session, user.id, lesson_id, objects=media_bucket()):
        raise HTTPException(status.HTTP_404_NOT_FOUND, NO_LESSON_DETAIL)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{lesson_id}/files/{fmt}")
async def get_lesson_file(
    lesson_id: uuid.UUID,
    fmt: LessonFormat,
    response: Response,
    *,
    user: User = Depends(require(Capability.BUILD_LESSONS)),
    session: AsyncSession = Depends(get_session),
    tools: ExportTools = Depends(export_tools),
) -> dict[str, Any]:
    pack = await lesson_of(session, user.id, lesson_id)
    if pack is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NO_LESSON_DETAIL)
    link = await lesson_file(session, tools, user.id, pack, fmt)
    response.headers["Cache-Control"] = PRIVATE_NO_CACHE
    return link.model_dump(mode="json", by_alias=True)


@router.get("/{lesson_id}/share")
async def get_lesson_share(
    lesson_id: uuid.UUID,
    response: Response,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    link = await lesson_share(session, user.id, lesson_id)
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NO_LESSON_DETAIL)
    response.headers["Cache-Control"] = PRIVATE_NO_CACHE
    return link.model_dump(mode="json", by_alias=True)


@router.put("/{lesson_id}/share")
async def put_lesson_share(
    lesson_id: uuid.UUID,
    response: Response,
    user: User = Depends(require(Capability.BUILD_LESSONS)),
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    try:
        link = await share_lesson(session, user.id, lesson_id, now=datetime.now(UTC))
    except NothingPublic:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, NOTHING_PUBLIC_DETAIL) from None
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, NO_LESSON_DETAIL)
    response.headers["Cache-Control"] = PRIVATE_NO_CACHE
    return link.model_dump(mode="json", by_alias=True)


@router.delete("/{lesson_id}/share", status_code=status.HTTP_204_NO_CONTENT)
async def delete_lesson_share(
    lesson_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    if not await unshare_lesson(session, user.id, lesson_id, objects=media_bucket()):
        raise HTTPException(status.HTTP_404_NOT_FOUND, NO_LESSON_DETAIL)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
