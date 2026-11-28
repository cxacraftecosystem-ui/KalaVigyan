from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any, Literal, Self

from pydantic import Field, field_serializer, model_validator

from app.core.errors import InvalidInput, NotConfigured
from app.core.mcp_scopes import CONTRIBUTE_SCOPE
from app.research.base import ContractModel
from app.research.crafts import SLUG_MAX_CHARS
from app.research.page_proposals import PageComponent
from app.services.compose_components import COMPOSED_KINDS, ComposeDeps, compose_component, compose_every_kind
from app.services.compose_held import About, Composition

from .mcp_guide_steps import HandedGuide, storyboard_guide
from .mcp_studio_arguments import STUDIO_DOES, StudioArguments
from .mcp_tool_base import LOOKS, PAGES, Arguments, Tool, ToolContext, contributor

__all__ = [
    "COMPOSE_COMPONENT",
    "COMPOSE_TOOLS",
    "ComposeAbout",
    "ComposeComponent",
    "ComposeReply",
    "compose_tools",
]

NAME = "compose_component"
ENTRY_KEY = r"^[A-Z]\d{2,4}$"
SLUG = r"^[A-Za-z0-9-]+$"
ONE_ABOUT = "name at most one of stage, reaction, material and compound"
ABOUT_ONE_KIND = "about narrows one kind: name the kind as well, or leave about out to compose every kind"
DESCRIPTION = (
    "Composes a craft's own interactive from the facts and structure its page holds, as the server builds it: "
    "reaction_player from its stored reactions in the order of their stages, dip_player from its stages in a "
    "bath with their colour after, drawn as the depicted colour of the dye, mordant or resist named, "
    "molecule_3d from a compound its materials hold, or one its facts name given by its PubChem CID, with "
    "PubChem's 3D conformer (atoms, bonds, turned and zoomed by pointer, touch and keyboard), experiment_lab from the alternatives its facts compare, with a "
    "toggle for each. Every state and label cites only that craft's own facts; nothing is borrowed from "
    "another page. about narrows it to one stage, reaction or material key or a compound's CID. The result is "
    "finished components ({proposal, cites}) in the shape a page draft's add takes; nothing is stored or "
    "proposed. When the facts are not enough it composes nothing and missing lists the facts or structure each "
    "kind still lacks; left_out names what it could not draw, each a stage, reaction, material or compound "
    "that can be composed with about once its facts are held, or a figure that needs coding. With no kind it "
    "composes every kind the craft's facts allow in one call, each finished, and missing names, kind by kind, "
    "what the rest still need."
)
COMPOSED = "Composed {count} component{s} for {slug} from its own facts."
EVERY = "Composed {count} component{s} for {slug} from its own facts: {kinds}."
REFUSED = "Nothing was composed for {slug}: propose what missing lists first, then compose again."
PLACE = (
    "Add the components to the page's draft with edit_draft (add.components, as they are), set task_key on "
    "the proposal if you claimed one, or set them aside where your own design says it better. Build the "
    "page's other figures (coded figures and the kinds of the cookbook, cookbook/1), lay the page out, call "
    "preview_page and read every picture of the report before propose_page; if propose_page names a close "
    "match, propose it again as a VARIANT that extends it."
)
PROPOSE = (
    "Propose each item of missing with propose_facts or propose_structure, then call compose_component again."
)


class ComposeAbout(Arguments):
    stage: str | None = Field(default=None, pattern=ENTRY_KEY, description="A stage key, such as S03")
    reaction: str | None = Field(default=None, pattern=ENTRY_KEY, description="A reaction key, such as R01")
    material: str | None = Field(default=None, pattern=ENTRY_KEY, description="A material key, such as M05")
    compound: int | None = Field(
        default=None, ge=1, description="A PubChem CID one of its materials holds or its facts name"
    )

    @model_validator(mode="after")
    def _one_at_most(self) -> Self:
        given = [
            value for value in (self.stage, self.reaction, self.material, self.compound) if value is not None
        ]
        if len(given) > 1:
            raise ValueError(ONE_ABOUT)
        return self

    def about(self) -> About:
        return About(stage=self.stage, reaction=self.reaction, material=self.material, compound=self.compound)


class ComposeComponent(StudioArguments):
    craft: str = Field(min_length=1, max_length=SLUG_MAX_CHARS, pattern=SLUG, description="The craft's slug")
    kind: Literal[*COMPOSED_KINDS] | None = Field(
        default=None, description=f"One of {', '.join(COMPOSED_KINDS)}; every kind when absent"
    )
    about: ComposeAbout | None = Field(default=None, description="What it is about, at most one key")

    @model_validator(mode="after")
    def _about_one_kind(self) -> Self:
        if self.about is not None and self.kind is None:
            raise ValueError(ABOUT_ONE_KIND)
        return self


class ComposeReply(ContractModel):
    craft: str
    kind: str | None
    composed: bool
    components: list[PageComponent] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)
    left_out: list[str] = Field(default_factory=list)
    message: str
    next_step: str
    notices: list[str] = Field(default_factory=list)
    guide: HandedGuide

    @field_serializer("components")
    def _as_edit_draft_takes_them(self, components: list[PageComponent]) -> list[dict[str, Any]]:
        return [component.model_dump(mode="json", by_alias=False) for component in components]


def _run(deps: ComposeDeps) -> Callable[[ToolContext, ComposeComponent], Awaitable[ComposeReply]]:
    async def run(context: ToolContext, arguments: ComposeComponent) -> ComposeReply:
        contributor(context, NAME, STUDIO_DOES)
        if arguments.kind is None:
            every = await compose_every_kind(context.session, deps, arguments.craft)
            return _reply(arguments, _gathered(every), _said(arguments.craft, every))
        about = arguments.about.about() if arguments.about is not None else About()
        try:
            result = await compose_component(context.session, deps, arguments.craft, arguments.kind, about)
        except NotConfigured as missing:
            raise InvalidInput(missing.message) from None
        count = len(result.components)
        said = COMPOSED.format(count=count, s="" if count == 1 else "s", slug=arguments.craft)
        return _reply(arguments, result, said if result.composed else None)

    return run


def _gathered(every: Mapping[str, Composition]) -> Composition:
    return Composition(
        components=tuple(component for result in every.values() for component in result.components),
        missing=tuple(f"{kind}: {item}" for kind, result in every.items() for item in result.missing),
        left_out=tuple(f"{kind}: {item}" for kind, result in every.items() for item in result.left_out),
    )


def _said(slug: str, every: Mapping[str, Composition]) -> str | None:
    kinds = [kind for kind, result in every.items() if result.composed]
    count = sum(len(every[kind].components) for kind in kinds)
    if not count:
        return None
    return EVERY.format(count=count, s="" if count == 1 else "s", slug=slug, kinds=", ".join(kinds))


def _reply(arguments: ComposeComponent, result: Composition, said: str | None) -> ComposeReply:
    return ComposeReply(
        craft=arguments.craft,
        kind=arguments.kind,
        composed=said is not None,
        components=list(result.components),
        missing=list(result.missing),
        left_out=list(result.left_out),
        message=said or REFUSED.format(slug=arguments.craft),
        next_step=PLACE if said is not None else PROPOSE,
        notices=arguments.notices(),
        guide=storyboard_guide(),
    )


def compose_tools(deps: ComposeDeps) -> tuple[Tool, ...]:
    return (
        Tool(
            NAME,
            "Compose a craft's own interactive",
            DESCRIPTION,
            ComposeComponent,
            ComposeReply,
            _run(deps),
            CONTRIBUTE_SCOPE,
            LOOKS,
            group=PAGES,
        ),
    )


COMPOSE_TOOLS = compose_tools(ComposeDeps())
COMPOSE_COMPONENT = COMPOSE_TOOLS[0]
