from __future__ import annotations

from datetime import UTC, datetime
from types import MappingProxyType
from typing import Annotated

from pydantic import Field

from app.core.errors import InvalidInput
from app.core.mcp_scopes import CONTRIBUTE_SCOPE
from app.models import User
from app.research.my_tasks import CLAIMS_PER_CALL_MAX, MyTasks, TaskClaims
from app.research.open_work import TASK_KEY_MAX_CHARS
from app.research.trust_tiers import ESTABLISHED, NEW, PROVEN, TIER_TASKS_HELD
from app.services import contribution_queue_tasks, task_reservations

from .mcp_argument_names import RenamedArguments
from .mcp_tool_base import READ_ONLY, WRITES, NoArguments, Tool, ToolContext

__all__ = ["CLAIM_TASKS", "MY_TASKS", "TASK_TOOLS", "ClaimTasks"]

SIGN_IN = "This tool needs a signed-in connection."
CLAIM_DESCRIPTION = (
    "Reserve several open tasks in one call, for two hours each as claim_task does; each key is claimed on "
    "its own, so a task that is taken, closed or over this account's cap is refused and the rest are held. "
    f"How many tasks an account holds at once is set by its trust tier (new {TIER_TASKS_HELD[NEW]}, "
    f"established {TIER_TASKS_HELD[ESTABLISHED]}, proven {TIER_TASKS_HELD[PROVEN]}; my_tasks says which). "
    "Claiming a held task again renews it."
)
TaskKey = Annotated[str, Field(min_length=1, max_length=TASK_KEY_MAX_CHARS)]
MINE_DESCRIPTION = (
    "This account's work in one view: the tasks it holds with their reservation ends and what each needs, "
    "the tasks it completed in the last 30 days, the outcomes of its latest proposals (queued, checking, "
    "published, waiting or refused, with each gate's reasons), its trust tier and how many tasks it may hold."
)


class ClaimTasks(RenamedArguments):
    OLD_NAMES = MappingProxyType({"taskKeys": "task_keys"})

    task_keys: list[TaskKey] = Field(
        min_length=1,
        max_length=CLAIMS_PER_CALL_MAX,
        description=f"Up to {CLAIMS_PER_CALL_MAX} task keys from list_open_work or my_crafts",
    )


async def _claim_tasks(context: ToolContext, arguments: ClaimTasks) -> TaskClaims:
    claims = await task_reservations.claim_tasks(
        context.session,
        _signed_in(context).id,
        list(arguments.task_keys),
        site=context.site,
        now=datetime.now(UTC),
    )
    return claims.model_copy(update={"notices": arguments.notices()})


async def _my_tasks(context: ToolContext, arguments: NoArguments) -> MyTasks:
    return await contribution_queue_tasks.my_tasks(
        context.session, _signed_in(context), site=context.site, now=datetime.now(UTC)
    )


def _signed_in(context: ToolContext) -> User:
    if context.user is None:
        raise InvalidInput(SIGN_IN)
    return context.user


CLAIM_TASKS = Tool(
    name="claim_tasks",
    title="Reserve several tasks",
    description=CLAIM_DESCRIPTION,
    arguments=ClaimTasks,
    output=TaskClaims,
    run=_claim_tasks,
    scope=CONTRIBUTE_SCOPE,
    annotations=WRITES,
)
MY_TASKS = Tool(
    name="my_tasks",
    title="List this account's tasks",
    description=MINE_DESCRIPTION,
    arguments=NoArguments,
    output=MyTasks,
    run=_my_tasks,
    scope=CONTRIBUTE_SCOPE,
    annotations=READ_ONLY,
)

TASK_TOOLS = (CLAIM_TASKS, MY_TASKS)
