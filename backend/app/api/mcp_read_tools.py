from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from app.research.crafts import QUESTION_MAX_CHARS, SLUG_MAX_CHARS
from app.research.knowledge_api import (
    FACTS_LIMIT_DEFAULT,
    FACTS_LIMIT_MAX,
    CraftComponents,
    CraftFacts,
    FoundCrafts,
)
from app.research.page_proposals import PageSubject
from app.research.vocabulary import Discipline, PieceKind
from app.services import category_knowledge, component_library, craft_finder, knowledge_api
from app.services.open_work_subjects import CATEGORY, subject_by_key

from .mcp_page_read import GET_PAGE
from .mcp_tool_base import Arguments, Tool, ToolContext

__all__ = ["READ_TOOLS"]

FIND_DESCRIPTION = (
    "Up to five crafts for a name, a local name, a place, a kind or what a craft is made of or done with "
    "(bell metal casting, indigo resist), ranked by the names and places matched and by the concepts, cited "
    "claims and components each craft holds, curated and covered crafts first; each with its slug, page and "
    "its cited claims per field: which fields are covered, thin or missing."
)
FACTS_DESCRIPTION = (
    "The cited facts of one craft, family or category page, optionally one field and ranked by words, each "
    "with its evidence level, verbatim quotes, locators, stored quantities and the figures resting on it; "
    "grouped by field with counts, and every field the page holds too few facts in named as open work with its "
    "task key. A category's are the facts its page links and those proposed for it."
)
ONE_PAGE = "name the page as subject {kind, slug} or give a craft_slug, one of them"
COMPONENTS_DESCRIPTION = (
    "The registered interactive components (players, maps, molecules, charts), each with its label, title, "
    "description, kind, fields and the subjects it is keyed to. Search it before delivering a component: one "
    "keyed to a concept, compound or place is shared by every craft it applies to, so place it by its label "
    "rather than making another."
)


class FindCrafts(Arguments):
    query: str = Field(
        min_length=1,
        max_length=QUESTION_MAX_CHARS,
        description="A craft's name, place or kind, or what it is made of or done with",
    )


class GetFacts(Arguments):
    craft_slug: str | None = Field(
        default=None, min_length=1, max_length=SLUG_MAX_CHARS, description="A craft's or family's slug"
    )
    subject: PageSubject | None = Field(
        default=None,
        description="The page instead: kind craft, family or category and its slug from find_crafts",
    )
    field: Discipline | None = Field(
        default=None, description="One of the sixteen fields; every field when absent"
    )
    query: str | None = Field(
        default=None, min_length=1, max_length=QUESTION_MAX_CHARS, description="Words to rank the facts by"
    )
    limit: int = Field(default=FACTS_LIMIT_DEFAULT, ge=1, le=FACTS_LIMIT_MAX)

    @model_validator(mode="after")
    def _one_page(self) -> Self:
        if (self.craft_slug is None) == (self.subject is None):
            raise ValueError(ONE_PAGE)
        return self


class ListComponents(Arguments):
    query: str | None = Field(
        default=None,
        min_length=1,
        max_length=QUESTION_MAX_CHARS,
        description="Words to search labels, titles and descriptions by, such as indigo reduction",
    )
    craft_slug: str | None = Field(
        default=None,
        min_length=1,
        max_length=SLUG_MAX_CHARS,
        description="A slug from find_crafts; also brings the shared components of its concepts, compounds and districts",
    )
    field: Discipline | None = Field(default=None, description="One of the sixteen fields")
    kind: PieceKind | None = Field(default=None, description="One kind of component")


async def _find_crafts(context: ToolContext, arguments: FindCrafts) -> FoundCrafts:
    return await craft_finder.find_crafts(context.session, context.index, arguments.query, site=context.site)


async def _get_facts(context: ToolContext, arguments: GetFacts) -> CraftFacts:
    if arguments.subject is None:
        return await _craft_facts(context, arguments, str(arguments.craft_slug))
    subject = await subject_by_key(context.session, arguments.subject.kind, arguments.subject.slug)
    if subject.kind != CATEGORY:
        return await _craft_facts(context, arguments, subject.slug)
    return await category_knowledge.category_facts(
        context.session,
        subject,
        site=context.site,
        field=arguments.field,
        query=arguments.query,
        limit=arguments.limit,
    )


async def _craft_facts(context: ToolContext, arguments: GetFacts, slug: str) -> CraftFacts:
    return await knowledge_api.craft_facts(
        context.session,
        slug,
        site=context.site,
        field=arguments.field,
        query=arguments.query,
        limit=arguments.limit,
        held=knowledge_api.held_facts_for(context.user),
    )


async def _list_components(context: ToolContext, arguments: ListComponents) -> CraftComponents:
    return await component_library.library_components(
        context.session,
        slug=arguments.craft_slug,
        field=arguments.field,
        kind=arguments.kind,
        query=arguments.query,
    )


READ_TOOLS: tuple[Tool, ...] = (
    Tool(
        "find_crafts",
        "Find crafts",
        FIND_DESCRIPTION,
        FindCrafts,
        FoundCrafts,
        _find_crafts,
        shows_output=True,
    ),
    GET_PAGE,
    Tool(
        "get_facts",
        "Get a page's facts",
        FACTS_DESCRIPTION,
        GetFacts,
        CraftFacts,
        _get_facts,
        shows_output=True,
    ),
    Tool(
        "list_components",
        "Search the component library",
        COMPONENTS_DESCRIPTION,
        ListComponents,
        CraftComponents,
        _list_components,
        shows_output=True,
    ),
)
