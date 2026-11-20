from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import Field

from app.core.mcp_scopes import CONTRIBUTE_SCOPE
from app.core.rate_limit import PAGE_PREVIEWS, PAGE_PROPOSALS
from app.data.page_preview_view import PAGE_PREVIEW_VIEW_URI
from app.models import PageDraft
from app.research.page_drafts import DraftAddition, DraftView, parts_counts
from app.research.page_proposals import PagePreviewResult, PageProposalResult, PageSubject
from app.research.page_report import PageReport
from app.research.review_switch import AGENT
from app.services import page_drafts, page_preview, page_report

from .mcp_ask_tools import ViewedTool
from .mcp_studio_arguments import AddToDraft, CreateDraft, DraftRef, RemoveFromDraft, contributor
from .mcp_studio_sources import SUPPLY_SOURCE
from .mcp_tool_base import READ_ONLY, WRITES, Tool, ToolContext
from .page_proposal_deps import page_proposed
from .proposal_limits import refuse_tool_when_spent

__all__ = ["STUDIO_TOOLS", "DraftPreviewReply", "DraftReply", "DraftSubmission"]

CREATED = "The draft for {kind} {slug} is open: build the page in it over as many calls as you need."
HELD = "The draft holds {facts} facts, {structure} structure items, {components} components and {pictures} pictures."
ADD = "Add facts, structure, components, a layout, pictures and supplied sources with add_to_draft."
PREVIEW = "Call preview_draft to see the page and its checklist report; fix each failure and preview again."
SUBMIT = "When the report holds no failure you can fix, call submit_draft."
SUBMITTED = "Follow each part with get_proposal or my_tasks; the draft stays readable until it expires."
CREATE_DESCRIPTION = (
    "Open a private draft of one craft, family or category page, kept for this account for 14 days after its last "
    "change (one open draft a page, ten at once, 600 kB each). An AI builds the page in it over many calls with "
    "add_to_draft, sees it with preview_draft and submits it once with submit_draft. Calling it again for the same "
    "page gives back the open draft. Give the page's own lists first: its mechanisms, its ambiguous terms and "
    "its signature fact, which the preview checks."
)
ADD_DESCRIPTION = (
    "Add parts to a draft: facts (as propose_fact takes them), structure items (as propose_structure takes "
    "them), finished components and dataset figures ({proposal, cites}, cites naming the draft's facts as "
    "fact:0, fact:1 and on), the layout, pictures (a contribution_id given with give_image, or a new picture's "
    "claim_ids and declaration), supplied sources (ids from supply_source) and the page's lists. Each part is "
    "checked for its shape and the draft for its limits (20 facts, 20 structure items, 10 components, 10 pictures, "
    "40 supplied sources, 600 kB); nothing is proposed until submit_draft."
)
REMOVE_DESCRIPTION = (
    "Remove one part of a draft by its kind and index as get_draft lists it. Removing a fact renumbers the later "
    "facts in every component and picture that names them; a fact still named by a part is kept until that part "
    "changes."
)
GET_DESCRIPTION = "Read a draft of this account whole: every part, the lists, the last preview and, once submitted, its outcome."
PREVIEW_DESCRIPTION = (
    "Preview a draft: assemble the page it would make, drawn exactly as the site draws it behind a private link "
    "for this account for 24 hours, and report it against the page checklist. Each of the 26 rules that can be "
    "checked mechanically passes or fails with its evidence (true counts, no repeated sentence or picture, every "
    "figure citing through its units, a lede of at most three sentences, every field in its chapter and dense, the "
    "signature fact told once, mechanisms told in depth, balanced elements, no admitted gap); the rest are listed "
    "for you to judge on the link. With it: coverage by field, figures and their kinds, sources by grade and "
    "pictures by licence. Clients that draw MCP Apps show the report from ui://kalavigyan/page-preview.html."
)
SUBMIT_DESCRIPTION = (
    "Submit a draft once: every part goes through propose_page's checks, part by part (facts through the gates, "
    "structure through its checks, components through the delivery checks, the layout against the page's "
    "version, pictures starting their uploads), each counted against its own hour's allowance. A refused part "
    "leaves the others standing; the report gives each part's outcome and id."
)


class DraftReply(DraftView):
    notices: list[str] = Field(default_factory=list)


class DraftPreviewReply(PagePreviewResult):
    draft_id: uuid.UUID
    report: PageReport | None = None
    notices: list[str] = Field(default_factory=list)


class DraftSubmission(PageProposalResult):
    draft_id: uuid.UUID
    next_step: str
    notices: list[str] = Field(default_factory=list)


def _reply(
    row: PageDraft, message: str, next_step: str, notices: list[str], *, full: bool = False
) -> DraftReply:
    view = page_drafts.draft_view(row, message=message, next_step=next_step, full=full)
    return DraftReply.model_validate({**view.model_dump(), "notices": notices})


def _held(row: PageDraft) -> str:
    counts = parts_counts(page_drafts.held_parts(row))
    return HELD.format(
        facts=counts.facts, structure=counts.structure, components=counts.components, pictures=counts.pictures
    )


async def _create(context: ToolContext, arguments: CreateDraft) -> DraftReply:
    user = contributor(context, "create_draft")
    now = datetime.now(UTC)
    subject = PageSubject(kind=arguments.subject_kind, slug=arguments.slug)
    row = await page_drafts.create_draft(context.session, user, subject, now=now)
    if arguments.lists is not None or arguments.note is not None:
        added = DraftAddition(lists=arguments.lists, note=arguments.note)
        row = await page_drafts.add_to_draft(context.session, user, row.id, added, now=now)
    message = CREATED.format(kind=row.subjectKind, slug=row.subjectSlug)
    return _reply(row, f"{message} {_held(row)}", ADD, arguments.notices())


async def _add(context: ToolContext, arguments: AddToDraft) -> DraftReply:
    user = contributor(context, "add_to_draft")
    row = await page_drafts.add_to_draft(
        context.session, user, arguments.draft_id, arguments.addition(), now=datetime.now(UTC)
    )
    return _reply(row, _held(row), PREVIEW, arguments.notices())


async def _remove(context: ToolContext, arguments: RemoveFromDraft) -> DraftReply:
    user = contributor(context, "remove_from_draft")
    removed = (arguments.part, arguments.index)
    row = await page_drafts.remove_from_draft(
        context.session, user, arguments.draft_id, removed, now=datetime.now(UTC)
    )
    return _reply(row, _held(row), PREVIEW, arguments.notices())


async def _get(context: ToolContext, arguments: DraftRef) -> DraftReply:
    user = contributor(context, "get_draft")
    row = await page_drafts.own_draft(
        context.session, user, arguments.draft_id, now=datetime.now(UTC), open_only=False
    )
    step = SUBMITTED if row.result else PREVIEW
    return _reply(row, _held(row), step, arguments.notices(), full=True)


async def _preview(context: ToolContext, arguments: DraftRef) -> DraftPreviewReply:
    user = contributor(context, "preview_draft")
    now = datetime.now(UTC)
    row = await page_drafts.own_draft(context.session, user, arguments.draft_id, now=now, lock=True)
    bundle = page_drafts.bundle_of(row)
    refuse_tool_when_spent(PAGE_PREVIEWS, user)
    previewed = await page_preview.preview_page(context.session, user, bundle, site=context.site, now=now)
    lists = page_drafts.held_parts(row).lists
    report = await page_report.preview_report(context.session, user, bundle, previewed, lists=lists, now=now)
    await page_drafts.record_preview(context.session, row, previewed, report)
    return DraftPreviewReply.model_validate(
        {**previewed.model_dump(), "draftId": row.id, "report": report, "notices": arguments.notices()}
    )


async def _submit(context: ToolContext, arguments: DraftRef) -> DraftSubmission:
    user = contributor(context, "submit_draft")
    now = datetime.now(UTC)
    row = await page_drafts.own_draft(context.session, user, arguments.draft_id, now=now, lock=True)
    bundle = page_drafts.bundle_of(row)
    refuse_tool_when_spent(PAGE_PROPOSALS, user)
    result = await page_proposed(context.session, bundle, user, origin=AGENT, site=context.site)
    await page_drafts.record_submission(context.session, row, result, now=now)
    return DraftSubmission.model_validate(
        {**result.model_dump(), "draftId": row.id, "nextStep": SUBMITTED, "notices": arguments.notices()}
    )


CREATE_DRAFT = Tool(
    "create_draft",
    "Open a page draft",
    CREATE_DESCRIPTION,
    CreateDraft,
    DraftReply,
    _create,
    CONTRIBUTE_SCOPE,
    WRITES,
)
ADD_TO_DRAFT = Tool(
    "add_to_draft",
    "Add to a page draft",
    ADD_DESCRIPTION,
    AddToDraft,
    DraftReply,
    _add,
    CONTRIBUTE_SCOPE,
    WRITES,
)
REMOVE_FROM_DRAFT = Tool(
    "remove_from_draft",
    "Remove from a page draft",
    REMOVE_DESCRIPTION,
    RemoveFromDraft,
    DraftReply,
    _remove,
    CONTRIBUTE_SCOPE,
    WRITES,
)
GET_DRAFT = Tool(
    "get_draft", "Read a page draft", GET_DESCRIPTION, DraftRef, DraftReply, _get, CONTRIBUTE_SCOPE, READ_ONLY
)
PREVIEW_DRAFT = ViewedTool(
    "preview_draft",
    "Preview a page draft",
    PREVIEW_DESCRIPTION,
    DraftRef,
    DraftPreviewReply,
    _preview,
    CONTRIBUTE_SCOPE,
    WRITES,
    PAGE_PREVIEW_VIEW_URI,
)
SUBMIT_DRAFT = Tool(
    "submit_draft",
    "Submit a page draft",
    SUBMIT_DESCRIPTION,
    DraftRef,
    DraftSubmission,
    _submit,
    CONTRIBUTE_SCOPE,
    WRITES,
)
STUDIO_TOOLS: tuple[Tool, ...] = (
    SUPPLY_SOURCE,
    CREATE_DRAFT,
    ADD_TO_DRAFT,
    REMOVE_FROM_DRAFT,
    GET_DRAFT,
    PREVIEW_DRAFT,
    SUBMIT_DRAFT,
)
