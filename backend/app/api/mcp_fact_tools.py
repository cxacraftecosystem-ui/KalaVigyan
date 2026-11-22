from __future__ import annotations

from datetime import UTC, datetime

from app.core.mcp_scopes import CONTRIBUTE_SCOPE
from app.research.contribution_queue import ProposalBatch, ProposalTicket
from app.research.review_switch import AGENT
from app.services import contribution_queue, contribution_queue_tickets
from app.services.contribution_queue import QueuedFact

from .mcp_fact_arguments import GetProposal, ProposeFacts
from .mcp_tool_base import (
    PROPOSING,
    READ_ONLY,
    WORK,
    WRITES,
    Tool,
    ToolContext,
    contributor,
    signed_in,
)

__all__ = ["FACT_TOOLS", "GET_PROPOSAL", "PROPOSE_FACTS", "ProposeFacts"]

PROPOSE_DESCRIPTION = (
    "Propose one to 25 facts about a craft (craft_slug) or a category (category_slug), each in one field with "
    "the verbatim quotes and sources that state it and an idempotency_key of yours: a call sent again with the "
    "same keys returns the same proposals. Read get_facts first: a held fact is refused. Each fact is checked "
    "on its own, so a malformed fact, an unknown subject, a key used before for another fact or a spent hourly "
    "allowance refuses that fact only. The gates run off the request in a queue: they fetch every source and "
    "re-find every quote, grade the source and read its licence, refuse a fact the subject holds or one that "
    "adds nothing to its section, and keep a disagreement with a held fact as sources differ; the judge is asked "
    "only when quotes, source and held facts cannot decide. The reply gives each fact by index its proposal id "
    "(QUEUED) or why it was refused; get_proposal or my_work report each outcome. Name the field or "
    "corroboration task you claimed as task_key: a fact that passes completes it, a refused one gives it back."
)
GET_DESCRIPTION = (
    "The state of one of this account's proposals: QUEUED with the number of proposals ahead of it, CHECKING "
    "while the gates run, DONE with the reply (published, waiting for a reviewer or refused, each gate's "
    "reasons, the fact's id, and readers: whether a signed-out reader sees the fact now, on which page and field, "
    "whether a written section cites it or which write-section task is open, or why readers cannot see it) and "
    "the model calls and cost the checks took, or FAILED when the checks could not run after five tries (nothing "
    "was stored; send it again with the same idempotency_key). Tell a person a fact is on the page only when "
    "readers.shown is true."
)


async def _propose_many(context: ToolContext, arguments: ProposeFacts) -> ProposalBatch:
    user = contributor(context, "propose_facts", "propose facts")
    queued = [
        QueuedFact(index=index, proposal=fact.fact(), key=fact.idempotency_key)
        for index, fact in arguments.indexed()
    ]
    batch = await contribution_queue.enqueue_facts(
        context.session, user, queued, origin=AGENT, now=datetime.now(UTC)
    )
    items = sorted([*batch.items, *arguments.refused()], key=lambda item: item.index)
    return contribution_queue.batch_of(items).model_copy(update={"notices": arguments.notices()})


async def _get_proposal(context: ToolContext, arguments: GetProposal) -> ProposalTicket:
    user = signed_in(context)
    return await contribution_queue_tickets.own_ticket(context.session, user, arguments.proposal_id)


PROPOSE_FACTS = Tool(
    name="propose_facts",
    title="Propose facts",
    description=PROPOSE_DESCRIPTION,
    arguments=ProposeFacts,
    output=ProposalBatch,
    run=_propose_many,
    scope=CONTRIBUTE_SCOPE,
    annotations=WRITES,
    group=PROPOSING,
)
GET_PROPOSAL = Tool(
    name="get_proposal",
    title="Get a proposal's progress",
    description=GET_DESCRIPTION,
    arguments=GetProposal,
    output=ProposalTicket,
    run=_get_proposal,
    scope=CONTRIBUTE_SCOPE,
    annotations=READ_ONLY,
    group=WORK,
)

FACT_TOOLS = (GET_PROPOSAL, PROPOSE_FACTS)
