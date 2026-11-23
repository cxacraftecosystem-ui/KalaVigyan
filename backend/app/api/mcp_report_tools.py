from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from typing import Any, Literal, Self

from pydantic import BaseModel, Field, model_validator

from app.core.errors import InvalidInput
from app.core.mcp_scopes import REVIEW_SCOPE
from app.core.roles import Capability, can
from app.models import User
from app.research.crafts import SLUG_MAX_CHARS
from app.research.mcp_activity import DEFAULT_PERIOD_DAYS, PERIOD_DAYS

from .mcp_report_pages import (
    CURSOR_PATTERN,
    FILTERS,
    LIMIT_DEFAULT,
    LIMIT_MAX,
    REPORT_FILTERS,
    REPORTS,
    ReportAsk,
)
from .mcp_report_reads import READERS
from .mcp_tool_base import ADMIN_GROUP, READ_ONLY, Arguments, Tool, ToolContext

__all__ = ["NOT_ADMIN", "REPORT_TOOLS", "AdminReport", "AdminReportArguments", "report_ask"]

NOT_ADMIN = "admin_reports is for Admins and Master Admins; this account cannot read them."
UNFIT_FILTERS = "the {report} report takes no {filters}"
DESCRIPTION = (
    "Read-only reports for Admins. coverage: each craft's field standings. hidden_facts: the nightly count of "
    "facts readers cannot see, by craft and reason. filing: where each live-research fact is filed against "
    "where today's rule would file it. sources: sources whose title is not a work's title or whose author is "
    "a file's producer. mcp_activity: MCP calls by tool and client, and the newest failures. spend: settled AI "
    "spend by India day and task. evaluations: the evaluation floors and any stored result."
)


class AdminReportArguments(Arguments):
    report: Literal[*REPORTS] = Field(description="Which report")
    craft_slug: str | None = Field(
        default=None,
        min_length=1,
        max_length=SLUG_MAX_CHARS,
        description="A craft's slug (coverage, hidden_facts)",
    )
    since: date | None = Field(default=None, description="Facts written on or after this day (filing)")
    answer_id: uuid.UUID | None = Field(default=None, description="Facts one answer wrote back (filing)")
    days: Literal[*PERIOD_DAYS] | None = Field(
        default=None, description=f"Days to read (mcp_activity, spend); {DEFAULT_PERIOD_DAYS} when left out"
    )
    cursor: str | None = Field(
        default=None, pattern=CURSOR_PATTERN, description="next_cursor of the last page"
    )
    limit: int = Field(default=LIMIT_DEFAULT, ge=1, le=LIMIT_MAX)

    @model_validator(mode="after")
    def _filters_fit(self) -> Self:
        given = [name for name in FILTERS if getattr(self, name) is not None]
        unfit = [name for name in given if name not in REPORT_FILTERS[self.report]]
        if unfit:
            raise ValueError(UNFIT_FILTERS.format(report=self.report, filters=", ".join(unfit)))
        return self


class AdminReport(BaseModel):
    report: str
    items: list[dict[str, Any]]
    total: int
    next_cursor: str | None
    message: str


def report_ask(arguments: AdminReportArguments, *, now: datetime) -> ReportAsk:
    return ReportAsk(
        now=now,
        craft=arguments.craft_slug,
        since=arguments.since,
        answer_id=arguments.answer_id,
        days=arguments.days if arguments.days is not None else DEFAULT_PERIOD_DAYS,
        offset=int(arguments.cursor) if arguments.cursor is not None else 0,
        limit=arguments.limit,
    )


def _admin(context: ToolContext) -> User:
    user = context.user
    if user is None or not can(user, Capability.REVIEW_CONTRIBUTIONS):
        raise InvalidInput(NOT_ADMIN)
    return user


async def _admin_reports(context: ToolContext, arguments: AdminReportArguments) -> AdminReport:
    _admin(context)
    page = await READERS[arguments.report](context, report_ask(arguments, now=datetime.now(UTC)))
    return AdminReport(
        report=arguments.report,
        items=page.items,
        total=page.total,
        next_cursor=page.next_cursor,
        message=page.message,
    )


REPORT_TOOLS: tuple[Tool, ...] = (
    Tool(
        "admin_reports",
        "Read the admin reports (Admins)",
        DESCRIPTION,
        AdminReportArguments,
        AdminReport,
        _admin_reports,
        REVIEW_SCOPE,
        READ_ONLY,
        group=ADMIN_GROUP,
    ),
)
