from __future__ import annotations

from datetime import UTC, datetime

from app.core.errors import InvalidInput
from app.core.mcp_scopes import CONTRIBUTE_SCOPE
from app.core.roles import Capability, can
from app.models import User
from app.research.contribution_queue import ProposalBatch, ProposalTicket
from app.research.review_switch import AGENT
from app.services import contribution_queue, contribution_queue_tickets
from app.services.contribution_queue import QueuedFact

from .mcp_fact_arguments import GetProposal, ProposeFact, ProposeFacts
from .mcp_tool_base import READ_ONLY, WRITES, Tool, ToolContext

__all__ = ["FACT_TOOLS", "GET_PROPOSAL", "PROPOSE_FACT", "PROPOSE_FACTS", "ProposeFact", "ProposeFacts"]

GATES = (
    "The gates run off the request, in a queue: they fetch every source and re-find every quote, grade the "
    "source and read its licence, refuse a fact the subject already holds or one that adds nothing to its "
    "section, and keep a disagreement with a held fact as sources differ; the judge is asked only when the "
    "quotes, the source and the texts and vectors of the held facts cannot decide. "
)
PROPOSE_DESCRIPTION = (
    "Propose one fact about a craft (craft_slug) or a category (category_slug) in one field, with the verbatim "
    "quotes and sources that state it. Call get_facts for the craft and field first: a fact already held is "
    "refused. "
    + GATES
    + "The reply comes at once with the proposal's id and its state (QUEUED); get_proposal with that id says "
    "whether the fact was published, waits for a reviewer, or was refused, with each gate's reasons. Give an "
    "idempotency_key so a retried call never adds the fact twice, and the field or corroboration task you "
    "claimed as task_key: a fact that passes completes it, and a refused one gives it back. The old form "
    "{proposal: {...}} still works until the next release and says so."
)
PROPOSE_MANY_DESCRIPTION = (
    "Propose up to 25 facts in one call, each as propose_fact takes one with its own idempotency_key. Each fact "
    "is checked on its own: a malformed fact, an unknown subject, a key given before for another fact or a "
    "spent hourly allowance refuses that fact only, and the rest are queued. "
    + GATES
    + "The reply lists every fact by its index with its proposal id and state, or why it was refused; "
    "get_proposal or my_tasks report each outcome. A retried call with the same keys returns the same proposals."
)
GET_DESCRIPTION = (
    "The state of one of this account's proposals: QUEUED with the number of proposals ahead of it, CHECKING "
    "while the gates run, DONE with the reply (published, waiting for a reviewer or refused, each gate's "
    "reasons, the fact's id) and the model calls and cost the checks took, or FAILED when the checks could not "
    "run after five tries (nothing was stored; send it again with the same idempotency_key)."
)
NEEDS_PROPOSER = "{tool} needs an account of Researcher or above; this account cannot propose facts."
SIGN_IN = "This tool needs a signed-in connection."


async def _propose(context: ToolContext, arguments: ProposeFact) -> ProposalTicket:
    user = _proposer(context, "propose_fact")
    queued = QueuedFact(index=0, proposal=arguments.fact(), key=arguments.idempotency_key)
    batch = await contribution_queue.enqueue_facts(
        context.session, user, [queued], origin=AGENT, now=datetime.now(UTC)
    )
    (item,) = batch.items
    if item.ticket is None:
        raise InvalidInput(item.problem or "The fact was refused.")
    return item.ticket.model_copy(update={"notices": arguments.notices()})


async def _propose_many(context: ToolContext, arguments: ProposeFacts) -> ProposalBatch:
    user = _proposer(context, "propose_facts")
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
    if context.user is None:
        raise InvalidInput(SIGN_IN)
    return await contribution_queue_tickets.own_ticket(context.session, context.user, arguments.proposal_id)


def _proposer(context: ToolContext, tool: str) -> User:
    user = context.user
    if user is None or not can(user, Capability.PROPOSE_KNOWLEDGE):
        raise InvalidInput(NEEDS_PROPOSER.format(tool=tool))
    return user


PROPOSE_FACT = Tool(
    name="propose_fact",
    title="Propose a fact",
    description=PROPOSE_DESCRIPTION,
    arguments=ProposeFact,
    output=ProposalTicket,
    run=_propose,
    scope=CONTRIBUTE_SCOPE,
    annotations=WRITES,
)
PROPOSE_FACTS = Tool(
    name="propose_facts",
    title="Propose several facts",
    description=PROPOSE_MANY_DESCRIPTION,
    arguments=ProposeFacts,
    output=ProposalBatch,
    run=_propose_many,
    scope=CONTRIBUTE_SCOPE,
    annotations=WRITES,
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
)

FACT_TOOLS = (PROPOSE_FACT, PROPOSE_FACTS, GET_PROPOSAL)
