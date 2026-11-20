from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import Field

from app.core.errors import InvalidInput, Refused
from app.core.mcp_scopes import CONTRIBUTE_SCOPE
from app.core.rate_limit import LAYOUT_PROPOSALS
from app.core.roles import Capability, can
from app.research.crafts import SLUG_MAX_CHARS
from app.research.layout_proposals import LayoutProposalDraft, LayoutProposalResult
from app.research.monograph_document import SUBJECT_KINDS
from app.research.page_layout import LayoutReply
from app.research.review_switch import AGENT
from app.services.open_work_subjects import subject_by_key
from app.services.page_layout_proposals import propose_layout
from app.services.page_layouts import layout_of, subject_path

from .mcp_tool_base import WRITES, Arguments, Tool, ToolContext
from .proposal_limits import refuse_tool_when_spent

__all__ = ["GET_LAYOUT", "LAYOUT_TOOLS", "PROPOSE_LAYOUT", "GetLayout", "ProposeLayout"]

GET_LAYOUT = "get_layout"
GET_LAYOUT_DESCRIPTION = (
    "The layout record of one craft, family or category page: for each placed text unit or component "
    "(by its unit id or component label) its chapter, its order in the chapter, its role (HERO, OPENER, "
    "PLATE, FIGURE, SIDEBAR, PULL_QUOTE or BODY), and for a picture its crop box, size and caption "
    "override. It never holds a fact: the facts are in get_facts and get_section, the components in "
    "list_components. layout is null where the page has none yet."
)
PROPOSE_LAYOUT = "propose_layout"
PROPOSE_LAYOUT_DESCRIPTION = (
    "Propose a new layout for one craft, family or category page: the whole list of entries the page should "
    "have, built on the version get_layout gave (baseVersion, 0 when the page has none). Each entry places a "
    "text unit or a component by its id or label in a chapter, with its order, role, and for a picture its "
    "crop, size and caption override; a layout never holds a fact. It waits in the review queue, and an "
    "Admin's approval writes it as the page's next version; it is refused when the page has moved on from "
    "baseVersion. Who proposed it is kept privately."
)
NEEDS_PROPOSER = (
    "propose_layout needs an account of Researcher or above; this account cannot propose layouts."
)


class GetLayout(Arguments):
    subject_kind: Literal[*SUBJECT_KINDS] = Field(description="craft, family or category")
    slug: str = Field(
        min_length=1,
        max_length=SLUG_MAX_CHARS,
        pattern=r"^[A-Za-z0-9-]+$",
        description="A craft's or family's slug from find_crafts, or a category's slug",
    )


async def _get_layout(context: ToolContext, arguments: GetLayout) -> LayoutReply:
    subject = await subject_by_key(context.session, arguments.subject_kind, arguments.slug)
    return LayoutReply(
        subject_kind=subject.kind,
        subject_slug=subject.slug,
        layout=await layout_of(context.session, subject),
        page_url=f"{context.site}{subject_path(subject)}",
    )


class ProposeLayout(Arguments):
    proposal: LayoutProposalDraft = Field(
        description=(
            "subject {kind craft, family or category, slug}, baseVersion (the version get_layout gave, 0 for "
            "none), entries [{ref, chapter, order, role, crop, size, caption}] and an optional note on why"
        )
    )


async def _propose_layout(context: ToolContext, arguments: ProposeLayout) -> LayoutProposalResult:
    user = context.user
    if user is None or not can(user, Capability.PROPOSE_KNOWLEDGE):
        raise InvalidInput(NEEDS_PROPOSER)
    await refuse_tool_when_spent(LAYOUT_PROPOSALS, user)
    try:
        return await propose_layout(
            context.session, user, arguments.proposal, origin=AGENT, site=context.site, now=datetime.now(UTC)
        )
    except Refused as refused:
        raise InvalidInput(refused.message) from None


LAYOUT_TOOLS: tuple[Tool, ...] = (
    Tool(GET_LAYOUT, "Get a page's layout", GET_LAYOUT_DESCRIPTION, GetLayout, LayoutReply, _get_layout),
    Tool(
        PROPOSE_LAYOUT,
        "Propose a page layout",
        PROPOSE_LAYOUT_DESCRIPTION,
        ProposeLayout,
        LayoutProposalResult,
        _propose_layout,
        scope=CONTRIBUTE_SCOPE,
        annotations=WRITES,
    ),
)
