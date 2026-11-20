from __future__ import annotations

from datetime import UTC, datetime
from typing import Self

from pydantic import Field, model_validator

from app.core.errors import InvalidInput
from app.core.mcp_scopes import CONTRIBUTE_SCOPE
from app.core.rate_limit import COMPONENT_PROPOSALS
from app.core.roles import Capability, can
from app.models import User
from app.research.component_proposals import SUBJECT_LINK, ComponentProposalDraft, ComponentProposalResult
from app.research.page_proposals import PageBundle, PagePreviewResult, PageProposalResult
from app.research.review_switch import AGENT
from app.services import component_proposals, page_preview

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
    "facts a unit rests on as fact:0, fact:1 and on), the page's layout (baseVersion and entries) and pictures "
    "(each starts an upload). Each part is checked on its own, as its own tool would check it, and stored when it "
    "passes; a refused part leaves the others standing. One report gives every part's outcome and reason. Call "
    "preview_page first to see the page the bundle makes."
)
PREVIEW_DESCRIPTION = (
    "Assemble the page a bundle would make, the stored page with the bundle's facts, structure, components and "
    "layout, without proposing anything, and return a private link to it: signed, for this account only, for 24 "
    "hours, drawn exactly as the site draws its pages. Each part reports whether it is shown, listed or would be "
    "refused by the checks that run without fetching sources; the gates read the sources when it is proposed."
)


class ProposeComponent(Arguments, ComponentProposalDraft):
    @model_validator(mode="after")
    def _delivered(self) -> Self:
        paired = (self.extends is None) == (self.extension is None)
        if paired and self.spec is None and self.extension != SUBJECT_LINK:
            raise ValueError(NEEDS_SPEC)
        return self


class ProposePage(Arguments):
    proposal: PageBundle = Field(
        description=(
            "subject {kind craft, family or category, slug}, and any of facts[], structure[], components[] "
            "({proposal, cites}), layout {baseVersion, entries}, pictures[] ({stageId, claimIds, declaration}), "
            "note"
        )
    )


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


async def _propose_page(context: ToolContext, arguments: ProposePage) -> PageProposalResult:
    user = _proposer(context, "propose_page")
    return await page_proposed(context.session, arguments.proposal, user, origin=AGENT, site=context.site)


async def _preview_page(context: ToolContext, arguments: ProposePage) -> PagePreviewResult:
    user = _proposer(context, "preview_page")
    return await page_preview.preview_page(
        context.session, user, arguments.proposal, site=context.site, now=datetime.now(UTC)
    )


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
    PageProposalResult,
    _propose_page,
    scope=CONTRIBUTE_SCOPE,
    annotations=WRITES,
)
PREVIEW_PAGE = Tool(
    "preview_page",
    "Preview a page bundle",
    PREVIEW_DESCRIPTION,
    ProposePage,
    PagePreviewResult,
    _preview_page,
    scope=CONTRIBUTE_SCOPE,
    annotations=WRITES,
)
PAGE_TOOLS: tuple[Tool, ...] = (PROPOSE_COMPONENT, PROPOSE_PAGE, PREVIEW_PAGE)
