from __future__ import annotations

from datetime import UTC, datetime
from typing import Self

from pydantic import Field, model_validator

from app.core.errors import InvalidInput
from app.core.mcp_scopes import CONTRIBUTE_SCOPE, REVIEW_SCOPE
from app.core.roles import role_value
from app.models import User
from app.research.crafts import SLUG_MAX_CHARS
from app.research.open_work import (
    TASK_KEY_MAX_CHARS,
    TASKS_LIMIT_DEFAULT,
    TASKS_LIMIT_MAX,
    OpenWork,
    Priority,
    TaskHold,
    TaskKind,
    Viewer,
    WorkFilters,
    several_subjects,
)
from app.research.vocabulary import Discipline
from app.services import open_work, task_reservations

from .mcp_tool_base import WRITES, Arguments, Tool, ToolContext

__all__ = ["WORK_TOOLS"]

SIGN_IN = "This tool needs a signed-in connection."


class ListOpenWork(Arguments):
    craft_slug: str | None = Field(
        default=None,
        min_length=1,
        max_length=SLUG_MAX_CHARS,
        description="One craft's tasks; a slug from find_crafts",
    )
    family_slug: str | None = Field(
        default=None,
        min_length=1,
        max_length=SLUG_MAX_CHARS,
        description="A family's page and the crafts of the family",
    )
    category_slug: str | None = Field(
        default=None,
        min_length=1,
        max_length=SLUG_MAX_CHARS,
        description="A category's page and every craft and family in it",
    )
    field: Discipline | None = Field(default=None, description="One of list_fields")
    kind: TaskKind | None = Field(default=None, description="One kind of task")
    priority: Priority | None = Field(default=None, description="HIGH, MEDIUM or LOW")
    limit: int = Field(default=TASKS_LIMIT_DEFAULT, ge=1, le=TASKS_LIMIT_MAX)

    @model_validator(mode="after")
    def _one_subject(self) -> Self:
        refusal = several_subjects(self.craft_slug, self.family_slug, self.category_slug)
        if refusal is not None:
            raise ValueError(refusal)
        return self


class TaskKeyArguments(Arguments):
    task_key: str = Field(
        min_length=1, max_length=TASK_KEY_MAX_CHARS, description="A task's key from list_open_work"
    )


async def _list_open_work(context: ToolContext, arguments: ListOpenWork) -> OpenWork:
    filters = WorkFilters.model_validate(arguments.model_dump())
    return await open_work.list_open_work(
        context.session, filters, _viewer(context), site=context.site, now=datetime.now(UTC)
    )


async def _claim_task(context: ToolContext, arguments: TaskKeyArguments) -> TaskHold:
    return await task_reservations.claim_task(
        context.session, _signed_in(context).id, arguments.task_key, site=context.site, now=datetime.now(UTC)
    )


async def _release_task(context: ToolContext, arguments: TaskKeyArguments) -> TaskHold:
    return await task_reservations.release_task(
        context.session, _signed_in(context).id, arguments.task_key, now=datetime.now(UTC)
    )


def _viewer(context: ToolContext) -> Viewer:
    if context.user is None:
        return Viewer()
    reviews = REVIEW_SCOPE in context.scopes
    return Viewer(user_id=context.user.id, review_role=role_value(context.user) if reviews else None)


def _signed_in(context: ToolContext) -> User:
    if context.user is None:
        raise InvalidInput(SIGN_IN)
    return context.user


WORK_TOOLS: tuple[Tool, ...] = (
    Tool(
        "list_open_work",
        "List the open work",
        "What still needs work, as tasks computed from each craft's, family's and category's completeness: "
        "missing or thin fields, sections to write from stored facts, missing components (What-if, molecules, "
        "map, reaction player, pictures), pages not yet in the monograph form, facts awaiting a second source, "
        "sources-differ entries, dead or unarchived sources, and for reviewers the review queues. Each task "
        "has its key, what is needed, its acceptance rule, its priority and the prompt that fits it, highest "
        "priority first. Tasks another account has reserved are left out.",
        ListOpenWork,
        OpenWork,
        _list_open_work,
    ),
    Tool(
        "claim_task",
        "Reserve a task",
        "Reserve an open task for this signed-in account for two hours so no other agent does the same work; "
        "claiming it again renews it, and an expired reservation returns the task to the list. How many "
        "tasks an account holds at once is set by its trust tier (my_tasks says it); claim_tasks reserves "
        "several in one call.",
        TaskKeyArguments,
        TaskHold,
        _claim_task,
        scope=CONTRIBUTE_SCOPE,
        annotations=WRITES,
    ),
    Tool(
        "release_task",
        "Give a task back",
        "Give back a task this account reserved, so it returns to the list at once.",
        TaskKeyArguments,
        TaskHold,
        _release_task,
        scope=CONTRIBUTE_SCOPE,
        annotations=WRITES,
    ),
)
