from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.proposal_limits import refuse_when_spent
from app.api.structure_proposal_deps import site_origin, structure_proposed
from app.core.db import get_session
from app.core.deps import require
from app.core.errors import ExternalFailure, InvalidInput, Refused
from app.core.rate_limit import STRUCTURE_PROPOSALS
from app.core.roles import Capability
from app.models import User
from app.research.review_switch import CONTRIBUTION
from app.research.structure_proposals import StructureProposal, StructureProposalResult
from app.services.own_proposals import require_terms
from app.services.structure_proposals_claims import MOVED_SOURCE
from app.services.structure_proposals_write import STALE_STRUCTURE

router = APIRouter(prefix="/knowledge", tags=["knowledge"])
proposer = require(Capability.PROPOSE_KNOWLEDGE)

CHECKS_UNAVAILABLE = "The checks could not run just now; nothing was stored. Try again in a minute."
CONFLICTING = frozenset({STALE_STRUCTURE, MOVED_SOURCE})


@router.post("/structure")
async def propose_page_structure(
    body: StructureProposal, user: User = Depends(proposer), session: AsyncSession = Depends(get_session)
) -> StructureProposalResult:
    try:
        await require_terms(session, user)
        await refuse_when_spent(STRUCTURE_PROPOSALS, user)
        return await structure_proposed(session, body, user, origin=CONTRIBUTION, site=site_origin())
    except InvalidInput as error:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(error)) from None
    except Refused as error:
        refused = status.HTTP_409_CONFLICT if error.reason in CONFLICTING else status.HTTP_403_FORBIDDEN
        raise HTTPException(refused, error.message) from None
    except ExternalFailure:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, CHECKS_UNAVAILABLE) from None
