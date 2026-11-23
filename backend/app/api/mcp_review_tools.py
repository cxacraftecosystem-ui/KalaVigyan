from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import Field, ValidationError

from app.core.errors import InvalidInput
from app.core.mcp_scopes import REVIEW_SCOPE
from app.core.roles import Capability, can
from app.models import ArtisanContribution, User
from app.research.base import ContractModel
from app.research.crafts import CraftRef
from app.research.page_refresh import CHANGED, MCP_ORIGIN, PageRefreshState
from app.research.review_labels import queue_label
from app.research.review_queue import ReviewFilters
from app.research.staged_reviews import BATCH_DAYS, MCP_QUEUE_KINDS, STAGED_ITEMS_PER_DAY_MAX, StagedDecision
from app.services.oauth_bearer import McpCaller
from app.services.page_refresh_jobs import RefreshAsk, RefreshRefused, refresh_state
from app.services.page_refresh_run import launch_refresh
from app.services.review_queue import QueueAdapters, list_review_queue, open_review_item
from app.services.review_queue_decisions import ItemRef
from app.services.staged_reviews import stage_decisions
from app.services.testimony_views import Turns

from .mcp_review_arguments import ReviewQueueArguments, StageArguments, StagedChoice
from .mcp_tool_base import ADMIN_GROUP, READ_ONLY, WRITES, Arguments, Tool, ToolContext

__all__ = ["REVIEW_TOOLS", "QueueReply", "RefreshReply", "StageReply"]

REVIEW_PAGE = "/admin/review"
NOT_AN_ADMIN = "{tool} is for Admin and Master Admin accounts signed in with the review scope."
NO_TRANSCRIPTS = "Testimony is reviewed on the site, not over MCP."
QUEUE_DESCRIPTION = (
    "Admins: list the review queue (facts, components, layouts, structure, readings, map layers, stages), "
    "filtered by kinds, craft and origin, newest first; or open one item whole with everything its card on "
    "the Review page shows: quotes, sources, gate checks, filing verdict, held reason and suggested craft. "
    "Re-read a source and check a quote with read_source. Testimony and pictures are reviewed on the site."
)
STAGE_DESCRIPTION = (
    "Admins: stage up to 20 decisions for a person to confirm. Nothing is published, changed or shown to "
    "readers until an Admin confirms the batch on the Review page; the server never applies what an app "
    "proposes. Each decision names the item's kind and id, an action the Review page allows (approve or "
    "reject; raise or retract a fact; approve a fact with craft or family to re-file it; correct a source's "
    "title, authors, year, journal or kind; clear a fact's sources-differ mark) and a reason of at least 12 "
    "characters. Each is checked by the rules the Review page applies; refused ones say why. "
    f"At most {STAGED_ITEMS_PER_DAY_MAX} a day; a batch expires after {BATCH_DAYS} days."
)
REFRESH_DESCRIPTION = (
    "Admins: read the page refresh, or start one with start true: it rebuilds the pages and stored documents "
    "that changed since the last refresh and refreshes them on the site, one job at a time, at most once in "
    "ten minutes. It calls no model. The reply gives the job's progress and outcome; call again to follow it."
)
STAGED_MESSAGE = (
    "Nothing is published yet. {count} decisions wait in a staged batch until an Admin confirms them on "
    "{url}, within {days} days. {refused}"
)
NONE_STAGED = "Nothing was staged: every decision was refused. Nothing is published or changed."
QUEUE_MESSAGE = (
    "{total} items wait. Decisions you stage with stage_reviews are not published until an Admin confirms "
    "them on {url}."
)


class QueueSummary(ContractModel):
    kind: str
    id: uuid.UUID
    origin: str
    submitted_at: datetime
    craft: CraftRef | None
    label: str


class QueueReply(ContractModel):
    kinds: list[str]
    counts: dict[str, int]
    total: int
    items: list[QueueSummary] = Field(default_factory=list)
    next_cursor: str | None = None
    item: dict[str, Any] | None = None
    message: str


class StagedLine(ContractModel):
    index: int
    kind: str
    id: uuid.UUID
    action: str | None = None
    label: str | None = None
    reason: str | None = None


class StageReply(ContractModel):
    batch_id: uuid.UUID | None
    staged: list[StagedLine]
    refused: list[StagedLine]
    staged_today: int
    per_day_max: int = STAGED_ITEMS_PER_DAY_MAX
    expires_at: datetime | None
    confirm_at: str
    published: bool = False
    message: str


class RefreshArguments(Arguments):
    start: bool = Field(default=False, description="Start a refresh of what changed")


class RefreshReply(ContractModel):
    state: PageRefreshState
    started: bool
    message: str


def _admin(context: ToolContext, tool: str) -> User:
    user = context.user
    if user is None or REVIEW_SCOPE not in context.scopes or not can(user, Capability.REVIEW_CONTRIBUTIONS):
        raise InvalidInput(NOT_AN_ADMIN.format(tool=tool))
    return user


def _caller(context: ToolContext, tool: str) -> McpCaller:
    _admin(context, tool)
    if context.caller is None:
        raise InvalidInput(NOT_AN_ADMIN.format(tool=tool))
    return context.caller


async def _no_transcripts(_: ArtisanContribution) -> Turns:
    raise InvalidInput(NO_TRANSCRIPTS)


ADAPTERS = QueueAdapters(objects=None, turns_of=_no_transcripts)


async def _review_queue(context: ToolContext, arguments: ReviewQueueArguments) -> QueueReply:
    user, now = _admin(context, "review_queue"), datetime.now(UTC)
    within = [kind for kind in MCP_QUEUE_KINDS if arguments.kinds is None or kind in arguments.kinds]
    filters = ReviewFilters(
        craft_slug=arguments.craft_slug,
        origin=arguments.origin,
        cursor=arguments.cursor,
        limit=arguments.limit,
    )
    page = await list_review_queue(context.session, user, filters, adapters=ADAPTERS, now=now, within=within)
    opened = None
    if arguments.open is not None:
        ref = ItemRef(arguments.open.kind, arguments.open.id)
        found = await open_review_item(context.session, user, ref, adapters=ADAPTERS, now=now)
        if found is None:
            raise InvalidInput(f"No {ref.kind.lower()} item you review has the id {ref.item_id}.")
        opened = found.model_dump(mode="json", by_alias=True)
    return QueueReply(
        kinds=list(page.kinds),
        counts=page.counts,
        total=page.total,
        items=[_summary(item) for item in page.items],
        next_cursor=page.next_cursor,
        item=opened,
        message=QUEUE_MESSAGE.format(total=page.total, url=f"{context.site}{REVIEW_PAGE}"),
    )


def _summary(item: Any) -> QueueSummary:
    return QueueSummary(
        kind=item.kind,
        id=item.id,
        origin=item.origin,
        submitted_at=item.submitted_at,
        craft=item.craft,
        label=queue_label(item),
    )


async def _stage_reviews(context: ToolContext, arguments: StageArguments) -> StageReply:
    caller, now = _caller(context, "stage_reviews"), datetime.now(UTC)
    read: list[tuple[int, StagedDecision]] = []
    refused: list[StagedLine] = []
    for index, choice in enumerate(arguments.decisions):
        try:
            read.append((index, _decision(choice)))
        except ValidationError as unread:
            reason = "; ".join(str(problem["msg"]) for problem in unread.errors())
            refused.append(StagedLine(index=index, kind=choice.kind, id=choice.id, reason=reason))
    staged = await stage_decisions(context.session, [decision for _, decision in read], caller, now=now)
    refused += [
        StagedLine(index=read[each.index][0], kind=each.kind, id=each.id, reason=each.reason)
        for each in staged.refused
    ]
    left_out = {each.index for each in staged.refused}
    asked_at = [index for position, (index, _) in enumerate(read) if position not in left_out]
    kept = [
        StagedLine(
            index=asked_at[item.position],
            kind=item.kind,
            id=item.itemId,
            action=item.action,
            label=item.label,
        )
        for item in staged.items
    ]
    url = f"{context.site}{REVIEW_PAGE}"
    return StageReply(
        batch_id=None if staged.batch is None else staged.batch.id,
        staged=kept,
        refused=sorted(refused, key=lambda line: line.index),
        staged_today=staged.today,
        expires_at=None if staged.batch is None else staged.batch.expiresAt,
        confirm_at=url,
        message=_staged_message(len(kept), len(refused), url),
    )


def _decision(choice: StagedChoice) -> StagedDecision:
    given = choice.model_dump(exclude_none=True, exclude={"craft_slug", "family_slug"})
    return StagedDecision.model_validate(given | {"craft": choice.craft_slug, "family": choice.family_slug})


def _staged_message(count: int, refused: int, url: str) -> str:
    if count == 0:
        return NONE_STAGED
    said = f"{refused} were refused; each says why." if refused else ""
    return STAGED_MESSAGE.format(count=count, url=url, days=BATCH_DAYS, refused=said).strip()


async def _refresh_pages(context: ToolContext, arguments: RefreshArguments) -> RefreshReply:
    user, now = _admin(context, "refresh_pages"), datetime.now(UTC)
    message = "This is the page refresh as it stands; start true starts one."
    started = False
    if arguments.start:
        caller = _caller(context, "refresh_pages")
        ask = RefreshAsk(CHANGED, MCP_ORIGIN, user, client_name=caller.client_name)
        if context.background is None:
            raise InvalidInput("This server cannot run a refresh from here; start it on the site's settings.")
        try:
            await launch_refresh(context.session, ask, context.background, now=now)
            started, message = True, "A refresh of what changed has started; call again to follow it."
        except RefreshRefused as refused:
            message = refused.message
    state = await refresh_state(context.session, user, now=datetime.now(UTC))
    return RefreshReply(state=state, started=started, message=message)


REVIEW_TOOLS: tuple[Tool, ...] = (
    Tool(
        "review_queue",
        "Read the review queue (Admins)",
        QUEUE_DESCRIPTION,
        ReviewQueueArguments,
        QueueReply,
        _review_queue,
        REVIEW_SCOPE,
        READ_ONLY,
        group=ADMIN_GROUP,
    ),
    Tool(
        "stage_reviews",
        "Stage review decisions for a person to confirm (Admins)",
        STAGE_DESCRIPTION,
        StageArguments,
        StageReply,
        _stage_reviews,
        REVIEW_SCOPE,
        WRITES,
        group=ADMIN_GROUP,
    ),
    Tool(
        "refresh_pages",
        "Refresh the pages that changed (Admins)",
        REFRESH_DESCRIPTION,
        RefreshArguments,
        RefreshReply,
        _refresh_pages,
        REVIEW_SCOPE,
        WRITES,
        group=ADMIN_GROUP,
    ),
)
