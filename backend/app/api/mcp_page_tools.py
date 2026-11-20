from __future__ import annotations

import uuid
from datetime import UTC, datetime

from pydantic import Field

from app.core.errors import InvalidInput
from app.core.mcp_scopes import CONTRIBUTE_SCOPE
from app.core.rate_limit import PAGE_PREVIEWS, PAGE_PROPOSALS
from app.data.page_preview_view import PAGE_PREVIEW_VIEW_URI
from app.models import PageDraft, User
from app.research.page_drafts import DraftView, PageLists, parts_counts
from app.research.page_proposals import PageBundle, PagePreviewResult, PageProposalResult
from app.research.page_report import PageReport
from app.research.review_switch import AGENT
from app.services import page_drafts, page_preview, page_report

from .mcp_page_arguments import ONE_PAGE, ONE_WORK, EditDraft, PageWork, bundle_parts
from .mcp_page_texts import (
    ADD,
    CREATED,
    EDIT_DESCRIPTION,
    FOLLOW,
    HELD,
    PREVIEW,
    PREVIEW_DESCRIPTION,
    PROPOSE_DESCRIPTION,
    SUBMITTED,
)
from .mcp_studio_arguments import STUDIO_DOES
from .mcp_tool_base import PAGES, READ_ONLY, WRITES, Tool, ToolContext, contributor
from .page_proposal_deps import page_proposed
from .proposal_limits import refuse_tool_when_spent

__all__ = ["PAGE_TOOLS", "DraftReply", "PageReply", "PreviewReply"]


class DraftReply(DraftView):
    notices: list[str] = Field(default_factory=list)


class PreviewReply(PagePreviewResult):
    draft_id: uuid.UUID | None = None
    report: PageReport | None = None
    notices: list[str] = Field(default_factory=list)


class PageReply(PageProposalResult):
    draft_id: uuid.UUID | None = None
    next_step: str | None = None
    notices: list[str] = Field(default_factory=list)


def _held(row: PageDraft) -> str:
    counts = parts_counts(page_drafts.held_parts(row))
    return HELD.format(
        facts=counts.facts, structure=counts.structure, components=counts.components, pictures=counts.pictures
    )


async def _opened(
    context: ToolContext, user: User, arguments: EditDraft, now: datetime
) -> tuple[PageDraft, str]:
    if arguments.draft_id is not None:
        changing = arguments.changes()
        row = await page_drafts.own_draft(
            context.session, user, arguments.draft_id, now=now, open_only=changing
        )
        return row, ""
    if arguments.subject is None:
        raise InvalidInput(ONE_PAGE)
    row = await page_drafts.create_draft(context.session, user, arguments.subject, now=now)
    return row, CREATED.format(kind=row.subjectKind, slug=row.subjectSlug) + " "


async def _edit_draft(context: ToolContext, arguments: EditDraft) -> DraftReply:
    user, now = contributor(context, "edit_draft", STUDIO_DOES), datetime.now(UTC)
    row, opened = await _opened(context, user, arguments, now)
    for removed in arguments.removals():
        row = await page_drafts.remove_from_draft(context.session, user, row.id, removed, now=now)
    addition = arguments.addition()
    if addition is not None:
        row = await page_drafts.add_to_draft(context.session, user, row.id, addition, now=now)
    changed = arguments.changes()
    step = SUBMITTED if row.result else (PREVIEW if changed else ADD)
    view = page_drafts.draft_view(row, message=f"{opened}{_held(row)}", next_step=step, full=not changed)
    return DraftReply.model_validate({**view.model_dump(), "notices": arguments.notices()})


async def _work(
    context: ToolContext, user: User, arguments: PageWork, now: datetime
) -> tuple[PageBundle, PageDraft | None, PageLists | None]:
    if arguments.draft_id is None:
        if arguments.bundle is None:
            raise InvalidInput(ONE_WORK)
        return arguments.bundle, None, None
    row = await page_drafts.own_draft(context.session, user, arguments.draft_id, now=now, lock=True)
    return page_drafts.bundle_of(row), row, page_drafts.held_parts(row).lists


async def _preview_page(context: ToolContext, arguments: PageWork) -> PreviewReply:
    user, now = contributor(context, "preview_page", STUDIO_DOES), datetime.now(UTC)
    bundle, row, lists = await _work(context, user, arguments, now)
    refuse_tool_when_spent(PAGE_PREVIEWS, user)
    previewed = await page_preview.preview_page(context.session, user, bundle, site=context.site, now=now)
    report = await page_report.preview_report(context.session, user, bundle, previewed, lists=lists, now=now)
    if row is not None:
        await page_drafts.record_preview(context.session, row, previewed, report)
    return PreviewReply.model_validate(
        {
            **previewed.model_dump(),
            "draftId": arguments.draft_id,
            "report": report,
            "notices": arguments.notices(),
        }
    )


async def _propose_page(context: ToolContext, arguments: PageWork) -> PageReply:
    user, now = contributor(context, "propose_page", STUDIO_DOES), datetime.now(UTC)
    bundle, row, _ = await _work(context, user, arguments, now)
    if row is not None or bundle_parts(bundle) > 1:
        refuse_tool_when_spent(PAGE_PROPOSALS, user)
    result = await page_proposed(context.session, bundle, user, origin=AGENT, site=context.site)
    if row is not None:
        await page_drafts.record_submission(context.session, row, result, now=now)
    return PageReply.model_validate(
        {
            **result.model_dump(),
            "draftId": arguments.draft_id,
            "nextStep": FOLLOW if row is None else SUBMITTED,
            "notices": arguments.notices(),
        }
    )


PAGE_TOOLS: tuple[Tool, ...] = (
    Tool(
        "edit_draft",
        "Build a page in a draft",
        EDIT_DESCRIPTION,
        EditDraft,
        DraftReply,
        _edit_draft,
        CONTRIBUTE_SCOPE,
        WRITES,
        group=PAGES,
    ),
    Tool(
        "preview_page",
        "Preview a page",
        PREVIEW_DESCRIPTION,
        PageWork,
        PreviewReply,
        _preview_page,
        CONTRIBUTE_SCOPE,
        READ_ONLY,
        group=PAGES,
        view=PAGE_PREVIEW_VIEW_URI,
        records=True,
        shows_output=True,
    ),
    Tool(
        "propose_page",
        "Propose a page or one of its parts",
        PROPOSE_DESCRIPTION,
        PageWork,
        PageReply,
        _propose_page,
        CONTRIBUTE_SCOPE,
        WRITES,
        group=PAGES,
    ),
)
