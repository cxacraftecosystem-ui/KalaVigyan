from __future__ import annotations

import uuid
from collections.abc import Awaitable
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.testimony_deps import audio_objects, conversation_turns
from app.core.db import get_session
from app.core.deps import get_current_user
from app.core.errors import InvalidInput
from app.models import ArtisanContribution, ArtisanConversation, User
from app.providers.embedding import router_embedder
from app.providers.router import Principal
from app.research.crafts import SLUG_MAX_CHARS
from app.research.review_queue import (
    CURSOR_MAX_CHARS,
    PAGE_DEFAULT,
    PAGE_MAX,
    FactLevelRaise,
    FactRetraction,
    QueueApproval,
    QueueDecision,
    QueueKind,
    QueueRejection,
    ReviewFilters,
    ReviewOrigin,
    ReviewQueuePage,
    reviewed_kinds,
)
from app.services import review_queue_decisions as decisions
from app.services.page_revalidation import refresh_pages
from app.services.review_queue import QueueAdapters, list_review_queue
from app.services.review_queue_errors import (
    DecisionConflict,
    NotYourQueue,
    OwnItem,
    UnknownCraft,
    UnknownItem,
)
from app.services.review_queue_refile import filed_owners
from app.services.review_queue_refresh import refresh_after_decision
from app.services.testimony_views import Turns
from app.services.written_vectors import embed_decided

router = APIRouter(prefix="/review-queue", tags=["review"])

NOT_A_REVIEWER = "The review queue is for Professors, Admins and Master Admins."
UNKNOWN_CRAFT = "No craft has that address."


async def queue_reviewer(user: User = Depends(get_current_user)) -> User:
    if not reviewed_kinds(user):
        raise HTTPException(status.HTTP_403_FORBIDDEN, NOT_A_REVIEWER)
    return user


def queue_filters(
    kind: QueueKind | None = None,
    craft: str | None = Query(None, min_length=1, max_length=SLUG_MAX_CHARS),
    origin: ReviewOrigin | None = None,
    cursor: str | None = Query(None, min_length=1, max_length=CURSOR_MAX_CHARS),
    limit: int = Query(PAGE_DEFAULT, ge=1, le=PAGE_MAX),
) -> ReviewFilters:
    return ReviewFilters(kind=kind, craft_slug=craft, origin=origin, cursor=cursor, limit=limit)


class _Transcripts:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._opened: dict[uuid.UUID, Turns] = {}

    async def __call__(self, contribution: ArtisanContribution) -> Turns:
        key = contribution.conversationId
        if key not in self._opened:
            self._opened[key] = conversation_turns(await self._session.get(ArtisanConversation, key))
        return self._opened[key]


@router.get("")
async def review_queue(
    filters: ReviewFilters = Depends(queue_filters),
    user: User = Depends(queue_reviewer),
    session: AsyncSession = Depends(get_session),
) -> ReviewQueuePage:
    adapters = QueueAdapters(objects=audio_objects(), turns_of=_Transcripts(session))
    try:
        return await list_review_queue(session, user, filters, adapters=adapters, now=_now())
    except UnknownCraft:
        raise HTTPException(status.HTTP_404_NOT_FOUND, UNKNOWN_CRAFT) from None
    except InvalidInput as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None


@router.post("/{kind}/{item_id}/approve")
async def approve(
    kind: QueueKind,
    item_id: uuid.UUID,
    body: QueueApproval,
    user: User = Depends(queue_reviewer),
    session: AsyncSession = Depends(get_session),
) -> QueueDecision:
    ref = decisions.ItemRef(kind, item_id)
    moved_from = await filed_owners(session, kind, item_id, body.filed_under)
    decided = await _decided(session, decisions.approve_item(session, ref, user, body, now=_now()))
    await refresh_pages(moved_from)
    await embed_decided(session, router_embedder(Principal(user_id=user.id, role=user.role)), decided)
    return decided


@router.post("/{kind}/{item_id}/reject")
async def reject(
    kind: QueueKind,
    item_id: uuid.UUID,
    body: QueueRejection,
    user: User = Depends(queue_reviewer),
    session: AsyncSession = Depends(get_session),
) -> QueueDecision:
    ref = decisions.ItemRef(kind, item_id)
    return await _decided(session, decisions.reject_item(session, ref, user, body, now=_now()))


@router.post("/FACTS/{claim_id}/raise")
async def raise_level(
    claim_id: uuid.UUID,
    body: FactLevelRaise,
    user: User = Depends(queue_reviewer),
    session: AsyncSession = Depends(get_session),
) -> QueueDecision:
    return await _decided(session, decisions.raise_fact(session, claim_id, user, body, now=_now()))


@router.post("/FACTS/{claim_id}/retract")
async def retract(
    claim_id: uuid.UUID,
    body: FactRetraction,
    user: User = Depends(queue_reviewer),
    session: AsyncSession = Depends(get_session),
) -> QueueDecision:
    return await _decided(session, decisions.retract_fact(session, claim_id, user, body, now=_now()))


def _now() -> datetime:
    return datetime.now(UTC)


async def _decided(session: AsyncSession, change: Awaitable[QueueDecision]) -> QueueDecision:
    try:
        decided = await change
    except UnknownItem as missing:
        await session.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(missing)) from None
    except (OwnItem, NotYourQueue) as refused:
        await session.rollback()
        raise HTTPException(status.HTTP_403_FORBIDDEN, str(refused)) from None
    except DecisionConflict as conflict:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, str(conflict)) from None
    except InvalidInput as invalid:
        await session.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(invalid)) from None
    await session.commit()
    await refresh_after_decision(session, decided)
    return decided
