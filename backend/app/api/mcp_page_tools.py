from __future__ import annotations

from datetime import UTC, datetime
from typing import Self

from pydantic import Field, model_validator

from app.core.errors import InvalidInput
from app.core.mcp_scopes import CONTRIBUTE_SCOPE
from app.core.rate_limit import COMPONENT_PROPOSALS, PAGE_PREVIEWS, PAGE_PROPOSALS
from app.core.roles import Capability, can
from app.models import User
from app.research.component_proposals import SUBJECT_LINK, ComponentProposalDraft, ComponentProposalResult
from app.research.page_proposals import PageBundle, PagePreviewResult, PageProposalResult
from app.research.review_switch import AGENT
from app.services import component_proposals, page_preview

from .mcp_argument_names import SnakeBodyArguments
from .mcp_tool_base import WRITES, Arguments, Tool, ToolContext
from .page_proposal_deps import page_proposed
from .proposal_limits import refuse_tool_when_spent

__all__ = [
    "PAGE_TOOLS",
    "PREVIEW_PAGE",
    "PROPOSE_COMPONENT",
    "PROPOSE_PAGE",
    "ProposeComponent",
    "ProposePage",
]

NEEDS_PROPOSER = (
    "{tool} needs an account of Researcher or above; this account cannot propose pages or components."
)
NEEDS_SPEC = (
    "a component is delivered finished: give its spec (the kind's spec data) and the units it places, each "
    "unit's text with the ids of the facts it rests on; only a SUBJECT_LINK carries none"
)
COMPONENT_DESCRIPTION = (
    "Deliver a finished component, or an extension of one, after searching the library with list_components; "
    "name the labels you considered. Give its spec, the data of its kind (any of the 42 kinds of the approved "
    "page, or a general kind for anything new: general_drawing, general_chart, general_table, general_timeline "
    "or general_map_layer), and units: each text the spec places by its unit id (u0001 and on), with the ids of "
    "the shown facts it rests on. The spec is checked against its kind's model, every unit's facts must be shown, "
    "every number a unit states must be in its facts, and a drawing's SVG is cleaned of scripts, event handlers, "
    "foreign objects and outside references. A close match in the library refuses it with the matches and two "
    "ways on, never a copy. Otherwise it waits for an Admin, whose approval registers it so every page it applies "
    "to draws it; a Professor's or Admin's own is registered at once. Who proposed it is kept privately."
)
PAGE_DESCRIPTION = (
    "Deliver one bundle for one craft, family or category page: facts (as propose_fact takes them), structure "
    "items (as propose_structure takes them), components (each {proposal, cites}, cites naming the bundle's "
    "facts a unit rests on as fact:0, fact:1 and on), the page's layout (base_version and entries) and pictures "
    "(a new one starts an upload, one given already is named by contribution_id). Each part is checked on its "
    "own, as its own tool would check it, and stored when it passes; a refused part leaves the others standing. "
    "One report gives every part's outcome and reason. Call preview_page first to see the page the bundle makes. "
    "Every name inside the bundle is snake_case; the old camelCase names work until the next release and say so "
    "in notices."
)
PREVIEW_DESCRIPTION = (
    "Assemble the page a bundle would make, the stored page with the bundle's facts, structure, components and "
    "layout, without proposing anything, and return a private link to it: signed, for this account only, for 24 "
    "hours, drawn exactly as the site draws its pages. Each part reports whether it is shown, listed or would be "
    "refused by the checks that run without fetching sources; the gates read the sources when it is proposed. "
    "A picture this account gave with give_image, named by its contribution_id, is drawn in its place."
)


class ProposeComponent(Arguments, ComponentProposalDraft):
    @model_validator(mode="after")
    def _delivered(self) -> Self:
        paired = (self.extends is None) == (self.extension is None)
        if paired and self.spec is None and self.extension != SUBJECT_LINK:
            raise ValueError(NEEDS_SPEC)
        return self


class ProposePage(SnakeBodyArguments):
    proposal: PageBundle = Field(
        description=(
            "subject {kind craft, family or category, slug}, and any of facts[], structure[], components[] "
            "({proposal, cites}), layout {base_version, entries}, pictures[] ({stage_id, claim_ids, "
            "declaration} for a new one, or {contribution_id} for one this account gave with give_image), note; "
            "the old camelCase names work until the next release and say so in notices"
        )
    )


class PageToolReply(PageProposalResult):
    notices: list[str] = Field(default_factory=list)


class PreviewToolReply(PagePreviewResult):
    notices: list[str] = Field(default_factory=list)


def _proposer(context: ToolContext, tool: str) -> User:
    user = context.user
    if user is None or not can(user, Capability.PROPOSE_KNOWLEDGE):
        raise InvalidInput(NEEDS_PROPOSER.format(tool=tool))
    return user


async def _propose_component(context: ToolContext, arguments: ProposeComponent) -> ComponentProposalResult:
    user = _proposer(context, "propose_component")
    refuse_tool_when_spent(COMPONENT_PROPOSALS, user)
    return await component_proposals.propose_component(
        context.session, user, arguments, now=datetime.now(UTC)
    )


async def _propose_page(context: ToolContext, arguments: ProposePage) -> PageToolReply:
    user = _proposer(context, "propose_page")
    refuse_tool_when_spent(PAGE_PROPOSALS, user)
    result = await page_proposed(context.session, arguments.proposal, user, origin=AGENT, site=context.site)
    return PageToolReply.model_validate({**result.model_dump(), "notices": arguments.notices()})


async def _preview_page(context: ToolContext, arguments: ProposePage) -> PreviewToolReply:
    user = _proposer(context, "preview_page")
    refuse_tool_when_spent(PAGE_PREVIEWS, user)
    result = await page_preview.preview_page(
        context.session, user, arguments.proposal, site=context.site, now=datetime.now(UTC)
    )
    return PreviewToolReply.model_validate({**result.model_dump(), "notices": arguments.notices()})


PROPOSE_COMPONENT = Tool(
    "propose_component",
    "Deliver a component",
    COMPONENT_DESCRIPTION,
    ProposeComponent,
    ComponentProposalResult,
    _propose_component,
    scope=CONTRIBUTE_SCOPE,
    annotations=WRITES,
)
PROPOSE_PAGE = Tool(
    "propose_page",
    "Deliver a page bundle",
    PAGE_DESCRIPTION,
    ProposePage,
    PageToolReply,
    _propose_page,
    scope=CONTRIBUTE_SCOPE,
    annotations=WRITES,
)
PREVIEW_PAGE = Tool(
    "preview_page",
    "Preview a page bundle",
    PREVIEW_DESCRIPTION,
    ProposePage,
    PreviewToolReply,
    _preview_page,
    scope=CONTRIBUTE_SCOPE,
    annotations=WRITES,
)
PAGE_TOOLS: tuple[Tool, ...] = (PROPOSE_COMPONENT, PROPOSE_PAGE, PREVIEW_PAGE)
