from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.testimony_deps import audio_objects, conversation_turns, refusal, testimony_errors
from app.core.db import get_session
from app.core.deps import require
from app.core.roles import Capability
from app.models import ArtisanContribution, ArtisanConversation, Craft, User
from app.research.testimony import CONTRIBUTION_STATUSES
from app.research.vocabulary import ANSWER_LANGUAGES
from app.schemas.testimony import EditBody
from app.services import knowledge_view, testimony_store, testimony_writes
from app.services.testimony_views import Turns, review_item

router = APIRouter(prefix="/testimony/review", tags=["testimony"])
reviewer = require(Capability.REVIEW_TESTIMONY)

UNKNOWN_CRAFT_DETAIL = "No craft has that address."
NO_TURN_DETAIL = "The words of this turn are no longer kept, so the quote cannot be changed."
CORROBORATION_MAX = 20
Status = Literal[*CONTRIBUTION_STATUSES]
Language = Literal[*ANSWER_LANGUAGES]


class _Transcripts:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._opened: dict[uuid.UUID, Turns] = {}

    async def of(self, contribution: ArtisanContribution) -> Turns:
        key = contribution.conversationId
        if key not in self._opened:
            self._opened[key] = conversation_turns(await self._session.get(ArtisanConversation, key))
        return self._opened[key]


async def _item(
    session: AsyncSession, contribution: ArtisanContribution, transcripts: _Transcripts
) -> dict[str, Any]:
    turns = await transcripts.of(contribution)
    return await review_item(session, contribution, turns=turns, links=audio_objects(), now=datetime.now(UTC))


async def _craft_id(session: AsyncSession, slug: str | None) -> uuid.UUID | None:
    if slug is None:
        return None
    craft = await knowledge_view.resolve_craft(session, slug)
    if craft is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, UNKNOWN_CRAFT_DETAIL)
    return craft.id


@router.get("")
async def review_queue(
    *,
    status_: Status = Query("PENDING", alias="status"),
    craft: str | None = Query(None, max_length=200),
    language: Language | None = None,
    cursor: str | None = Query(None, max_length=12),
    user: User = Depends(reviewer),
    session: AsyncSession = Depends(get_session),
) -> Any:
    try:
        page = await testimony_store.review_page(
            session,
            status=status_,
            craft_id=await _craft_id(session, craft),
            language=language,
            cursor=cursor,
            reviewer_id=user.id,
        )
    except testimony_errors as error:
        return refusal(error)
    transcripts = _Transcripts(session)
    items = [await _item(session, row, transcripts) for row in page.rows]
    return {"counts": page.counts, "total": page.total, "items": items, "nextCursor": page.next_cursor}


@router.get("/{contribution_id}")
async def review_one(
    contribution_id: uuid.UUID, user: User = Depends(reviewer), session: AsyncSession = Depends(get_session)
) -> Any:
    contribution = await session.get(ArtisanContribution, contribution_id)
    if contribution is None:
        return refusal(testimony_store.UnknownContribution(str(contribution_id)))
    return await _item(session, contribution, _Transcripts(session))


@router.put("/{contribution_id}")
async def edit_contribution(
    contribution_id: uuid.UUID,
    body: EditBody,
    user: User = Depends(reviewer),
    session: AsyncSession = Depends(get_session),
) -> Any:
    transcripts = _Transcripts(session)
    try:
        current = await testimony_store.contribution_for_update(session, contribution_id)
        turn = (await transcripts.of(current)).get(str(current.turnId))
        if turn is None or not turn.get("text"):
            return refusal(testimony_store.ContributionProblems([NO_TURN_DETAIL]))
        change = testimony_writes.ContributionEdit(
            version=body.version,
            quote=body.quote,
            english=body.english,
            english_checked=body.englishChecked,
            claim_text=body.claimText,
            discipline=body.discipline,
            concept_type=body.conceptType,
            concept_name=body.conceptName,
        )
        edited = await testimony_writes.edit(
            session, contribution_id, user, change=change, turn_text=str(turn["text"]), now=datetime.now(UTC)
        )
    except testimony_errors as error:
        await session.rollback()
        return refusal(error)
    await session.commit()
    return await _item(session, edited, transcripts)


@router.get("/{contribution_id}/corroboration")
async def corroboration_candidates(
    contribution_id: uuid.UUID,
    q: str = Query("", max_length=200),
    user: User = Depends(reviewer),
    session: AsyncSession = Depends(get_session),
) -> Any:
    contribution = await session.get(ArtisanContribution, contribution_id)
    craft = await session.get(Craft, contribution.craftId) if contribution is not None else None
    if contribution is None or craft is None:
        return refusal(testimony_store.UnknownContribution(str(contribution_id)))
    views, _sources = await knowledge_view.claims_for(session, craft, mode="HYBRID", question=q or None)
    ranked = sorted((view for view in views if not q or view.rank > 0), key=lambda view: -view.rank)
    claims = [
        {"id": str(view.id), "text": view.text, "level": view.level, "citation": view.citations[0]}
        for view in ranked[:CORROBORATION_MAX]
        if view.citations
    ]
    return {"claims": claims}
