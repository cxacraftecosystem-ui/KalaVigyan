from __future__ import annotations

from datetime import UTC, datetime

from pydantic import Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import ExternalFailure, InvalidInput
from app.core.mcp_scopes import CONTRIBUTE_SCOPE
from app.core.rate_limit import FACT_PROPOSALS
from app.core.roles import Capability, can
from app.models import User
from app.research.review_switch import AGENT
from app.research.source_proposals import ADDED, SourceProposal, SourceProposalReply
from app.services.candidate_sources import proposal_fetcher
from app.services.claim_pages import refresh_claim_pages
from app.services.source_proposals import SourceAsk, propose_source

from .mcp_argument_names import SnakeBodyArguments
from .mcp_tool_base import WRITES, Tool, ToolContext
from .proposal_limits import refuse_tool_when_spent

__all__ = ["PROPOSE_SOURCE", "SOURCE_TOOLS", "ProposeSource", "SourceToolReply", "source_proposed"]

PROPOSE_DESCRIPTION = (
    "Give a held or thinly supported fact a new source: the fact keeps its statement, and each quote you give "
    "must state it. The gates fetch every source and re-find every quote verbatim, and grade the source; quotes "
    "that pass are added to the fact at once. A fact held from its page because its quotes are no longer found "
    "returns to the page when a new quote passes. Use it for RESOURCE_FACT, CORROBORATE_FACT, "
    "FIND_ANOTHER_SOURCE, SECOND_SOURCE and DEAD_SOURCE tasks, naming the task you claimed as task_key and the "
    "fact as claim_id, its id from the task's fact ids or get_facts. An archived snapshot of a dead page "
    "(https://web.archive.org/web/<timestamp>/<url>) is a source like any other. Every name inside the proposal "
    "is snake_case; the old camelCase names work until the next release and say so in notices."
)
NEEDS_PROPOSER = (
    "propose_source needs an account of Researcher or above; this account cannot propose sources."
)
CHECKS_UNAVAILABLE = (
    "The checks could not run just now and nothing was stored; call propose_source again later."
)


class ProposeSource(SnakeBodyArguments):
    proposal: SourceProposal = Field(
        description=(
            "claim_id (the fact), sources [{url, title, licence, quotes [{text, locator}]}] and the task_key you "
            "claimed"
        )
    )


class SourceToolReply(SourceProposalReply):
    notices: list[str] = Field(default_factory=list)


async def source_proposed(
    session: AsyncSession, proposal: SourceProposal, user: User, *, origin: str, site: str
) -> SourceProposalReply:
    async with proposal_fetcher() as fetcher:
        try:
            ask = SourceAsk(proposer=user, origin=origin, fetcher=fetcher, site=site, now=datetime.now(UTC))
            reply = await propose_source(session, proposal, ask)
        except Exception:
            await session.rollback()
            raise
    await session.commit()
    if reply.outcome == ADDED:
        await refresh_claim_pages(session, [reply.claim_id])
    return reply


async def _propose(context: ToolContext, arguments: ProposeSource) -> SourceToolReply:
    user = context.user
    if user is None or not can(user, Capability.PROPOSE_KNOWLEDGE):
        raise InvalidInput(NEEDS_PROPOSER)
    refuse_tool_when_spent(FACT_PROPOSALS, user)
    try:
        reply = await source_proposed(
            context.session, arguments.proposal, user, origin=AGENT, site=context.site
        )
    except ExternalFailure:
        raise InvalidInput(CHECKS_UNAVAILABLE) from None
    return SourceToolReply.model_validate({**reply.model_dump(), "notices": arguments.notices()})


PROPOSE_SOURCE = Tool(
    name="propose_source",
    title="Propose a source for a fact",
    description=PROPOSE_DESCRIPTION,
    arguments=ProposeSource,
    output=SourceToolReply,
    run=_propose,
    scope=CONTRIBUTE_SCOPE,
    annotations=WRITES,
)

SOURCE_TOOLS = (PROPOSE_SOURCE,)
