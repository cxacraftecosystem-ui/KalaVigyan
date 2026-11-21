from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.proposal_deps import proposed
from app.api.proposal_limits import refuse_when_spent
from app.core.config import get_settings
from app.core.db import get_session
from app.core.deps import require
from app.core.errors import ExternalFailure, InvalidInput, Refused
from app.core.rate_limit import FACT_PROPOSALS, LAYOUT_PROPOSALS
from app.core.roles import Capability
from app.models import User
from app.research.knowledge_writes import FactProposal, ProposalReply
from app.research.layout_proposals import LayoutProposalDraft, LayoutProposalResult
from app.research.review_switch import CONTRIBUTION, ReviewSwitchUpdate, ReviewSwitchView
from app.services import app_settings, audit
from app.services.own_proposals import require_terms
from app.services.page_layout_proposals import propose_layout
from app.services.page_layouts import STALE_LAYOUT

router = APIRouter(prefix="/knowledge", tags=["knowledge"])
proposer = require(Capability.PROPOSE_KNOWLEDGE)
switch_keeper = require(Capability.REVIEW_CONTRIBUTIONS)

CHECKS_UNAVAILABLE = "The checks could not run just now; nothing was stored. Try again in a minute."
SWITCH_ACTION = "settings.review_switch_updated"


@router.post("/facts")
async def propose(
    body: FactProposal, user: User = Depends(proposer), session: AsyncSession = Depends(get_session)
) -> ProposalReply:
    try:
        await require_terms(session, user)
        await refuse_when_spent(FACT_PROPOSALS, user)
        return await proposed(session, body, user, CONTRIBUTION)
    except InvalidInput as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None
    except Refused as error:
        raise HTTPException(status.HTTP_403_FORBIDDEN, error.message) from None
    except ExternalFailure:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, CHECKS_UNAVAILABLE) from None


@router.post("/layouts")
async def propose_page_layout(
    body: LayoutProposalDraft, user: User = Depends(proposer), session: AsyncSession = Depends(get_session)
) -> LayoutProposalResult:
    try:
        await require_terms(session, user)
        await refuse_when_spent(LAYOUT_PROPOSALS, user)
        result = await propose_layout(
            session, user, body, origin=CONTRIBUTION, site=_site(), now=datetime.now(UTC)
        )
    except InvalidInput as error:
        await session.rollback()
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None
    except Refused as error:
        await session.rollback()
        raise HTTPException(_refusal_status(error), error.message) from None
    await session.commit()
    return result


@router.get("/review-switch")
async def get_review_switch(
    _: User = Depends(switch_keeper), session: AsyncSession = Depends(get_session)
) -> ReviewSwitchView:
    return ReviewSwitchView(current=await app_settings.review_switch(session))


@router.put("/review-switch")
async def set_review_switch(
    body: ReviewSwitchUpdate,
    actor: User = Depends(switch_keeper),
    session: AsyncSession = Depends(get_session),
) -> ReviewSwitchView:
    switch = await app_settings.set_review_switch(session, body, actor.id)
    await audit.record(
        session,
        action=SWITCH_ACTION,
        actor=actor,
        target_type="AppSetting",
        target_id=app_settings.REVIEW_SWITCH,
        detail={"switch": switch.stored()},
    )
    await session.commit()
    return ReviewSwitchView(current=switch)


def _refusal_status(error: Refused) -> int:
    return status.HTTP_409_CONFLICT if error.reason == STALE_LAYOUT else status.HTTP_403_FORBIDDEN


def _site() -> str:
    return get_settings().public_web_url.rstrip("/")
