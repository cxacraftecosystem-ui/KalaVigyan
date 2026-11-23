from __future__ import annotations

import uuid
from collections.abc import Awaitable
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.deps import get_current_user
from app.core.errors import InvalidInput
from app.core.roles import Capability, can
from app.models import User
from app.providers.embedding import router_embedder
from app.providers.router import Principal
from app.research.staged_reviews import StagedBatchList, StagedBatchView, StagedConfirmation
from app.services.page_refresh_run import refresh_named
from app.services.review_queue_errors import DecisionConflict, NotYourQueue, UnknownItem
from app.services.staged_review_confirm import confirm_batch, discard_batch
from app.services.staged_review_views import batch_view, open_batches
from app.services.written_vectors import embed_decided

router = APIRouter(prefix="/review-queue/staged", tags=["review"])

NOT_AN_ADMIN = "Staged review decisions are for Admins and Master Admins."


async def staged_reviewer(user: User = Depends(get_current_user)) -> User:
    if not can(user, Capability.REVIEW_CONTRIBUTIONS):
        raise HTTPException(status.HTTP_403_FORBIDDEN, NOT_AN_ADMIN)
    return user


@router.get("")
async def staged_batches(
    _: User = Depends(staged_reviewer), session: AsyncSession = Depends(get_session)
) -> StagedBatchList:
    return await open_batches(session, now=_now())


@router.post("/{batch_id}/confirm")
async def confirm_staged(
    request: Request,
    batch_id: uuid.UUID,
    body: StagedConfirmation,
    user: User = Depends(staged_reviewer),
    session: AsyncSession = Depends(get_session),
) -> StagedBatchView:
    confirmed = await _changed(session, confirm_batch(session, batch_id, body, user, now=_now()))
    background = request.app.state.shielded_work
    note = await refresh_named(session, confirmed.owners, user, background, now=_now())
    embed = router_embedder(Principal(user_id=user.id, role=user.role))
    for decided in confirmed.decided:
        await embed_decided(session, embed, decided)
    return await batch_view(session, confirmed.batch, now=_now(), refresh=note)


@router.post("/{batch_id}/discard")
async def discard_staged(
    batch_id: uuid.UUID, user: User = Depends(staged_reviewer), session: AsyncSession = Depends(get_session)
) -> StagedBatchView:
    batch = await _changed(session, discard_batch(session, batch_id, user, now=_now()))
    return await batch_view(session, batch, now=_now())


def _now() -> datetime:
    return datetime.now(UTC)


async def _changed[T](session: AsyncSession, change: Awaitable[T]) -> T:
    try:
        result = await change
    except UnknownItem as missing:
        await session.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(missing)) from None
    except NotYourQueue as refused:
        await session.rollback()
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(refused)) from None
    except DecisionConflict as conflict:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(conflict)) from None
    except InvalidInput as invalid:
        await session.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(invalid)) from None
    await session.commit()
    return result
