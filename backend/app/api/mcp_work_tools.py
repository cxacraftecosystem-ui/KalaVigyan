from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal, Self

from pydantic import Field, model_validator

from app.core.errors import InvalidInput, Refused
from app.core.mcp_scopes import CONTRIBUTE_SCOPE, REVIEW_SCOPE
from app.core.roles import Capability, can, role_value
from app.research.crafts import SLUG_MAX_CHARS
from app.research.my_tasks import CLAIMS_PER_CALL_MAX, MyTasks, RefusedClaim, TaskClaims
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
from app.research.stewardship import STEWARD_CRAFTS_MAX, StewardPackage, Stewardship
from app.research.trust_tiers import ESTABLISHED, NEW, PROVEN, TIER_TASKS_HELD
from app.research.vocabulary import Discipline
from app.services import contribution_queue_tasks, open_work, stewardship, task_reservations

from .mcp_tool_base import (
    READ_ONLY,
    WORK,
    WRITES,
    Arguments,
    NoArguments,
    Tool,
    ToolContext,
    contributor,
    signed_in,
)

__all__ = ["WORK_TOOLS", "MyWork", "ReservedTasks", "StewardReply"]

ADOPT, DROP = STEWARD_ACTIONS = ("adopt", "drop")
GAVE_BACK = "Gave back {released} tasks and refused {refused}; this account now holds {count} of its {most}."
ADOPTED = "This account stewards {slug}; its tasks not open at your last look come first, as new gaps."
NOT_STEWARD = "Stewardship is for accounts of Researcher or above; this account holds only its tasks."
LIST_DESCRIPTION = (
    "What still needs work, as tasks computed from each craft's, family's and category's completeness: missing "
    "or thin fields, sections to write from stored facts, missing components (What-if, molecules, map, reaction "
    "player, pictures), pages not yet in the monograph form, facts awaiting a second source, sources-differ "
    "entries, dead or unarchived sources, and for reviewers the review queues. Each task has its key, what is "
    "needed, its acceptance rule, its priority and the prompt that fits it, highest priority first. Tasks "
    "another account has reserved are left out."
)
MINE_DESCRIPTION = (
    "This account's work in one view: the tasks it holds with their reservation ends and what each needs, the "
    "tasks it completed in the last 30 days, the outcomes of its latest proposals (queued, checking, published, "
    "waiting or refused, with each gate's reasons), its trust tier and how many tasks it may hold, and each "
    "craft it stewards with its open work, the tasks opened since the last look first. Reading it records what "
    "you have now seen, so the next call's new gaps are the ones opened after it."
)
RESERVE_DESCRIPTION = (
    "Reserve open tasks for this account for two hours each so no other agent does the same work, and give "
    "back the ones you stop: release returns each at once, then claim reserves each key on its own, so a task "
    "that is taken, closed or over this account's cap is refused and the rest are held. Claiming a held task "
    "again renews it; an expired reservation returns the task to the list. How many tasks an account holds at "
    f"once is set by its trust tier (new {TIER_TASKS_HELD[NEW]}, established {TIER_TASKS_HELD[ESTABLISHED]}, "
    f"proven {TIER_TASKS_HELD[PROVEN]})."
)
STEWARD_DESCRIPTION = (
    "Adopt a craft or family as its steward, and its open work comes back as one package with the gaps opened "
    "since your last look first; or drop it, and its open work stays open to everyone. Stewardship never "
    f"reserves a task and never blocks anyone else. An account stewards at most {STEWARD_CRAFTS_MAX} crafts."
)

TaskKey = Annotated[str, Field(min_length=1, max_length=TASK_KEY_MAX_CHARS)]


class ListOpenWork(Arguments):
    craft_slug: str | None = Field(
        default=None,
        min_length=1,
        max_length=SLUG_MAX_CHARS,
        description="One craft's tasks, from find_crafts",
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
    field: Discipline | None = Field(default=None, description="One of the sixteen fields")
    kind: TaskKind | None = Field(default=None, description="One kind of task")
    priority: Priority | None = Field(default=None, description="HIGH, MEDIUM or LOW")
    limit: int = Field(default=TASKS_LIMIT_DEFAULT, ge=1, le=TASKS_LIMIT_MAX)

    @model_validator(mode="after")
    def _one_subject(self) -> Self:
        refusal = several_subjects(self.craft_slug, self.family_slug, self.category_slug)
        if refusal is not None:
            raise ValueError(refusal)
        return self


class ReserveTasks(Arguments):
    claim: list[TaskKey] = Field(
        default_factory=list, max_length=CLAIMS_PER_CALL_MAX, description="Task keys to reserve"
    )
    release: list[TaskKey] = Field(
        default_factory=list, max_length=CLAIMS_PER_CALL_MAX, description="Task keys this account gives back"
    )

    @model_validator(mode="after")
    def _something(self) -> Self:
        if not (self.claim or self.release):
            raise ValueError("name task keys to claim, to release, or both")
        return self


class StewardCraft(Arguments):
    craft_slug: str = Field(
        min_length=1, max_length=SLUG_MAX_CHARS, description="A craft's or family's slug from find_crafts"
    )
    action: Literal[*STEWARD_ACTIONS] = Field(description="adopt or drop")


class MyWork(MyTasks):
    crafts: list[StewardPackage] = Field(default_factory=list)
    crafts_max: int = STEWARD_CRAFTS_MAX
    message: str


class ReservedTasks(TaskClaims):
    released: list[TaskHold] = Field(default_factory=list)


class StewardReply(Stewardship):
    package: StewardPackage | None = None


def _viewer(context: ToolContext) -> Viewer:
    if context.user is None:
        return Viewer()
    reviews = REVIEW_SCOPE in context.scopes
    return Viewer(user_id=context.user.id, review_role=role_value(context.user) if reviews else None)


async def _list_open_work(context: ToolContext, arguments: ListOpenWork) -> OpenWork:
    filters = WorkFilters.model_validate(arguments.model_dump())
    return await open_work.list_open_work(
        context.session, filters, _viewer(context), site=context.site, now=datetime.now(UTC)
    )


async def _my_work(context: ToolContext, arguments: NoArguments) -> MyWork:
    user, now = signed_in(context), datetime.now(UTC)
    tasks = await contribution_queue_tasks.my_tasks(context.session, user, site=context.site, now=now)
    if not can(user, Capability.PROPOSE_KNOWLEDGE):
        return MyWork.model_validate({**tasks.model_dump(), "message": NOT_STEWARD})
    crafts = await stewardship.my_crafts(context.session, user, site=context.site, now=now)
    return MyWork.model_validate(
        {
            **tasks.model_dump(),
            "crafts": crafts.crafts,
            "crafts_max": crafts.adopted_max,
            "message": crafts.message,
        }
    )


async def _reserve_tasks(context: ToolContext, arguments: ReserveTasks) -> ReservedTasks:
    user, now = signed_in(context), datetime.now(UTC)
    released: list[TaskHold] = []
    refused: list[RefusedClaim] = []
    for key in dict.fromkeys(arguments.release):
        try:
            released.append(await task_reservations.release_task(context.session, user.id, key, now=now))
        except (InvalidInput, Refused) as problem:
            said = problem.message if isinstance(problem, Refused) else str(problem)
            refused.append(RefusedClaim(task_key=key, problem=said))
    claims = await task_reservations.claim_tasks(
        context.session, user.id, list(arguments.claim), site=context.site, now=now
    )
    message = claims.message
    if not arguments.claim:
        message = GAVE_BACK.format(
            released=len(released), refused=len(refused), count=claims.holding, most=claims.holding_max
        )
    return ReservedTasks.model_validate(
        {
            **claims.model_dump(),
            "refused": [*refused, *claims.refused],
            "released": released,
            "message": message,
        }
    )


async def _steward_craft(context: ToolContext, arguments: StewardCraft) -> StewardReply:
    user, now = contributor(context, "steward_craft"), datetime.now(UTC)
    if arguments.action == DROP:
        dropped = await stewardship.drop_craft(context.session, user, arguments.craft_slug, now=now)
        return StewardReply.model_validate(dropped.model_dump())
    package = await stewardship.adopt_craft(
        context.session, user, arguments.craft_slug, site=context.site, now=now
    )
    slug = package.craft.slug
    return StewardReply(craft_slug=slug, adopted=True, message=ADOPTED.format(slug=slug), package=package)


WORK_TOOLS: tuple[Tool, ...] = (
    Tool(
        "list_open_work",
        "List the open work",
        LIST_DESCRIPTION,
        ListOpenWork,
        OpenWork,
        _list_open_work,
        group=WORK,
    ),
    Tool(
        "my_work",
        "This account's work",
        MINE_DESCRIPTION,
        NoArguments,
        MyWork,
        _my_work,
        CONTRIBUTE_SCOPE,
        READ_ONLY,
        group=WORK,
        records=True,
    ),
    Tool(
        "reserve_tasks",
        "Reserve or give back tasks",
        RESERVE_DESCRIPTION,
        ReserveTasks,
        ReservedTasks,
        _reserve_tasks,
        CONTRIBUTE_SCOPE,
        WRITES,
        group=WORK,
    ),
    Tool(
        "steward_craft",
        "Adopt or drop a craft",
        STEWARD_DESCRIPTION,
        StewardCraft,
        StewardReply,
        _steward_craft,
        CONTRIBUTE_SCOPE,
        WRITES,
        group=WORK,
    ),
)
