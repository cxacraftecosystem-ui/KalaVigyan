from __future__ import annotations

from pydantic import Field

from app.core.errors import ExternalFailure, InvalidInput, Refused
from app.core.mcp_scopes import CONTRIBUTE_SCOPE
from app.core.rate_limit import STRUCTURE_PROPOSALS
from app.core.roles import Capability, can
from app.research.review_switch import AGENT
from app.research.structure_proposals import StructureProposal, StructureProposalResult

from .mcp_tool_base import WRITES, Arguments, Tool, ToolContext
from .proposal_limits import refuse_tool_when_spent
from .structure_proposal_deps import structure_proposed

__all__ = ["PROPOSE_STRUCTURE", "STRUCTURE_TOOLS", "ProposeStructure"]

PROPOSE_DESCRIPTION = (
    "Propose one piece of a curated craft page's structure, with the fact and the verbatim quotes that state it: "
    "a stage's after (STAGE_AFTER: what the work looks like after the stage, and its colours) or why "
    "(STAGE_WHY), a native name of the craft as a source names it (NATIVE_NAME), a reaction as a source states "
    "it (REACTION), a material's botanical name (BOTANICAL_NAME), a glossary term (GLOSSARY_TERM), an open "
    "question (OPEN_QUESTION), parts of the GI record (GI_RECORD), or two or more held facts of the page that "
    "disagree (CONFLICT, which names the facts by id and gives no new fact). Read the page with get_facts and "
    "get_section first: stage and material keys are the page's own. Every name, colour and number the item "
    "gives must be in one of its quotes; the gates fetch every source and re-find every quote, and grade the "
    "source. It waits in the review queue, and approval writes it into the page and its dossier. Name the field "
    "task you claimed as taskKey: a proposal that passes the checks completes it."
)
NEEDS_PROPOSER = (
    "propose_structure needs an account of Researcher or above; this account cannot propose structure."
)
CHECKS_UNAVAILABLE = (
    "The checks could not run just now and nothing was stored; call propose_structure again later."
)


class ProposeStructure(Arguments):
    proposal: StructureProposal = Field(
        description=(
            "subject {kind craft, slug}, item {kind and its parts}, field, statement (one sentence), sources "
            "[{url, title, licence, language, quotes [{text, locator}]}], the taskKey you claimed and an "
            "optional note; a CONFLICT item gives about and claimIds and no field, statement or sources"
        )
    )


async def _propose(context: ToolContext, arguments: ProposeStructure) -> StructureProposalResult:
    user = context.user
    if user is None or not can(user, Capability.PROPOSE_KNOWLEDGE):
        raise InvalidInput(NEEDS_PROPOSER)
    refuse_tool_when_spent(STRUCTURE_PROPOSALS, user)
    try:
        return await structure_proposed(
            context.session, arguments.proposal, user, origin=AGENT, site=context.site
        )
    except Refused as refused:
        raise InvalidInput(refused.message) from None
    except ExternalFailure:
        raise InvalidInput(CHECKS_UNAVAILABLE) from None


PROPOSE_STRUCTURE = Tool(
    name="propose_structure",
    title="Propose page structure",
    description=PROPOSE_DESCRIPTION,
    arguments=ProposeStructure,
    output=StructureProposalResult,
    run=_propose,
    scope=CONTRIBUTE_SCOPE,
    annotations=WRITES,
)

STRUCTURE_TOOLS = (PROPOSE_STRUCTURE,)
