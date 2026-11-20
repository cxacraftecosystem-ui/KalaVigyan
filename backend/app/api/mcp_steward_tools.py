from __future__ import annotations

from datetime import UTC, datetime

from pydantic import Field

from app.core.errors import InvalidInput
from app.core.mcp_scopes import CONTRIBUTE_SCOPE
from app.core.roles import Capability, can
from app.models import User
from app.research.crafts import SLUG_MAX_CHARS
from app.research.stewardship import STEWARD_CRAFTS_MAX, MyCrafts, StewardPackage, Stewardship
from app.services import stewardship

from .mcp_argument_names import RenamedArguments
from .mcp_tool_base import WRITES, NoArguments, Tool, ToolContext

__all__ = ["ADOPT_CRAFT", "DROP_CRAFT", "MY_CRAFTS", "STEWARD_TOOLS", "CraftArguments"]

NEEDS_CONTRIBUTOR = "{tool} needs an account of Researcher or above, which may contribute."
ADOPT_DESCRIPTION = (
    "Adopt a craft or family as its steward: its open work comes back as one package, with the gaps that "
    "opened since your last look first. Stewardship never reserves a task and never blocks anyone else; "
    f"claim tasks with claim_task or claim_tasks. An account stewards at most {STEWARD_CRAFTS_MAX} crafts."
)
DROP_DESCRIPTION = "Stop stewarding a craft; its open work stays open to everyone."
MINE_DESCRIPTION = (
    "Each craft this account stewards with its open work as one package: the tasks that opened since your "
    "last look first (new gaps), then the rest, and how many accounts steward it. Calling it records what "
    "you have now seen, so the next call's new gaps are the ones opened after this one."
)


class CraftArguments(RenamedArguments):
    craft_slug: str = Field(
        min_length=1, max_length=SLUG_MAX_CHARS, description="A craft's or family's slug from find_crafts"
    )


async def _adopt(context: ToolContext, arguments: CraftArguments) -> StewardPackage:
    return await stewardship.adopt_craft(
        context.session,
        _contributor(context, "adopt_craft"),
        arguments.craft_slug,
        site=context.site,
        now=datetime.now(UTC),
    )


async def _drop(context: ToolContext, arguments: CraftArguments) -> Stewardship:
    return await stewardship.drop_craft(
        context.session, _contributor(context, "drop_craft"), arguments.craft_slug, now=datetime.now(UTC)
    )


async def _mine(context: ToolContext, arguments: NoArguments) -> MyCrafts:
    return await stewardship.my_crafts(
        context.session, _contributor(context, "my_crafts"), site=context.site, now=datetime.now(UTC)
    )


def _contributor(context: ToolContext, tool: str) -> User:
    user = context.user
    if user is None or not can(user, Capability.PROPOSE_KNOWLEDGE):
        raise InvalidInput(NEEDS_CONTRIBUTOR.format(tool=tool))
    return user


ADOPT_CRAFT = Tool(
    name="adopt_craft",
    title="Adopt a craft",
    description=ADOPT_DESCRIPTION,
    arguments=CraftArguments,
    output=StewardPackage,
    run=_adopt,
    scope=CONTRIBUTE_SCOPE,
    annotations=WRITES,
)
DROP_CRAFT = Tool(
    name="drop_craft",
    title="Drop a craft",
    description=DROP_DESCRIPTION,
    arguments=CraftArguments,
    output=Stewardship,
    run=_drop,
    scope=CONTRIBUTE_SCOPE,
    annotations=WRITES,
)
MY_CRAFTS = Tool(
    name="my_crafts",
    title="List the crafts this account stewards",
    description=MINE_DESCRIPTION,
    arguments=NoArguments,
    output=MyCrafts,
    run=_mine,
    scope=CONTRIBUTE_SCOPE,
    annotations=WRITES,
)

STEWARD_TOOLS = (ADOPT_CRAFT, DROP_CRAFT, MY_CRAFTS)
