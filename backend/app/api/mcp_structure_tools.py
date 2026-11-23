from __future__ import annotations

from pydantic import Field

from app.core.errors import ExternalFailure, InvalidInput, Refused
from app.core.mcp_scopes import CONTRIBUTE_SCOPE
from app.core.rate_limit import STRUCTURE_PROPOSALS
from app.core.roles import Capability, can
from app.research.review_switch import AGENT
from app.research.structure_proposals import StructureProposal, StructureProposalResult

from .mcp_argument_names import SnakeBodyArguments
from .mcp_tool_base import PROPOSING, WRITES, Tool, ToolContext
from .proposal_limits import refuse_tool_when_spent
from .structure_proposal_deps import structure_proposed

__all__ = ["PROPOSE_STRUCTURE", "STRUCTURE_TOOLS", "ProposeStructure", "StructureToolReply"]

PROPOSE_DESCRIPTION = (
    "Propose one piece of a curated page's structure with the fact and the verbatim quotes that state it: a "
    "stage's after (STAGE_AFTER, with colours) or why (STAGE_WHY), a native name (NATIVE_NAME), a reaction "
    "(REACTION), a material's botanical name (BOTANICAL_NAME) or stand-in (ALTERNATIVE), a glossary term "
    "(GLOSSARY_TERM), an open question (OPEN_QUESTION), GI record parts (GI_RECORD), held facts that disagree "
    "(CONFLICT: their ids, no new fact), or a community or person a source names (GROUP_NAME: sources only, "
    "any craft; kept out of AI pictures, never shown). A category takes a reaction without a stage, a term, a "
    "question or a conflict. Stage and material keys are the page's own (get_facts, get_page). Every name, "
    "colour and number must be in a quote; the gates re-find every quote and grade each source. It waits for "
    "review; approval writes it into the page and its dossier. A passing proposal completes the field task "
    "you claimed as task_key. Names are snake_case."
)
NEEDS_PROPOSER = (
    "propose_structure needs an account of Researcher or above; this account cannot propose structure."
)
CHECKS_UNAVAILABLE = (
    "The checks could not run just now and nothing was stored; call propose_structure again later."
)


class ProposeStructure(SnakeBodyArguments):
    proposal: StructureProposal = Field(
        description=(
            "subject {kind, slug}, item (its kind and parts, such as stage_key), field, statement (one sentence), "
            "sources [{url, title, licence, language, quotes [{text, locator}]}], the task_key you claimed, an "
            "optional note; CONFLICT gives no field, statement or sources, GROUP_NAME sources only"
        )
    )


class StructureToolReply(StructureProposalResult):
    notices: list[str] = Field(default_factory=list)


async def _propose(context: ToolContext, arguments: ProposeStructure) -> StructureToolReply:
    user = context.user
    if user is None or not can(user, Capability.PROPOSE_KNOWLEDGE):
        raise InvalidInput(NEEDS_PROPOSER)
    await refuse_tool_when_spent(STRUCTURE_PROPOSALS, user)
    try:
        result = await structure_proposed(
            context.session, arguments.proposal, user, origin=AGENT, site=context.site
        )
    except Refused as refused:
        raise InvalidInput(refused.message) from None
    except ExternalFailure:
        raise InvalidInput(CHECKS_UNAVAILABLE) from None
    return StructureToolReply.model_validate({**result.model_dump(), "notices": arguments.notices()})


PROPOSE_STRUCTURE = Tool(
    name="propose_structure",
    title="Propose page structure",
    description=PROPOSE_DESCRIPTION,
    arguments=ProposeStructure,
    output=StructureToolReply,
    run=_propose,
    scope=CONTRIBUTE_SCOPE,
    annotations=WRITES,
    group=PROPOSING,
)

STRUCTURE_TOOLS = (PROPOSE_STRUCTURE,)
