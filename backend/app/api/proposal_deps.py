from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import User
from app.providers.embedding import router_embedder
from app.providers.router import Principal
from app.providers.structured import router_structured_model
from app.research.fetcher import Fetcher
from app.research.knowledge_writes import FactProposal, ProposalReply
from app.services.ai_providers import AiTask
from app.services.candidate_sources import proposal_fetcher
from app.services.claim_pages import published_claims, refresh_claim_pages
from app.services.fact_proposals import ProposalAdapters, propose_fact

__all__ = ["JUDGE_TASK", "gate_adapters", "proposed"]

JUDGE_TASK = AiTask.EVAL_JUDGE


def gate_adapters(user: User, fetcher: Fetcher) -> ProposalAdapters:
    principal = Principal(user_id=user.id, role=user.role)
    return ProposalAdapters(
        fetcher=fetcher,
        embed=router_embedder(principal),
        judge=router_structured_model(JUDGE_TASK, principal),
    )


async def proposed(session: AsyncSession, proposal: FactProposal, user: User, origin: str) -> ProposalReply:
    async with proposal_fetcher() as fetcher:
        try:
            reply = await propose_fact(
                session, proposal, user, origin, adapters=gate_adapters(user, fetcher), now=datetime.now(UTC)
            )
        except Exception:
            await session.rollback()
            raise
    await session.commit()
    await refresh_claim_pages(session, published_claims(reply))
    return reply
