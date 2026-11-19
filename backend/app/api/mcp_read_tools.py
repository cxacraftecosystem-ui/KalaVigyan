from __future__ import annotations

from typing import Self

from pydantic import Field, model_validator

from app.research.crafts import QUESTION_MAX_CHARS, SLUG_MAX_CHARS
from app.research.knowledge_api import (
    FACTS_LIMIT_DEFAULT,
    FACTS_LIMIT_MAX,
    CraftComponents,
    CraftFacts,
    CraftSection,
    FieldList,
    FoundCrafts,
    SubjectCoverage,
)
from app.research.vocabulary import Discipline, PieceKind
from app.services import component_library, coverage_reads, knowledge_api

from .mcp_tool_base import Arguments, Tool, ToolContext

__all__ = ["READ_TOOLS"]

CRAFT, CATEGORY = "craft", "category"
ONE_SUBJECT = "name a craft_slug or a category_slug, one of them"


class ListFields(Arguments):
    craft_slug: str | None = Field(
        default=None,
        min_length=1,
        max_length=SLUG_MAX_CHARS,
        description="A slug from find_crafts; each field then carries what that craft holds in it",
    )


class FindCrafts(Arguments):
    query: str = Field(
        min_length=1, max_length=QUESTION_MAX_CHARS, description="A craft's name, place or kind"
    )


class GetFacts(Arguments):
    craft_slug: str = Field(min_length=1, max_length=SLUG_MAX_CHARS, description="A slug from find_crafts")
    field: Discipline | None = Field(default=None, description="One of list_fields; every field when absent")
    query: str | None = Field(
        default=None, min_length=1, max_length=QUESTION_MAX_CHARS, description="Words to rank the facts by"
    )
    limit: int = Field(default=FACTS_LIMIT_DEFAULT, ge=1, le=FACTS_LIMIT_MAX)


class GetSection(Arguments):
    craft_slug: str = Field(min_length=1, max_length=SLUG_MAX_CHARS)
    field: Discipline | None = Field(
        default=None, description="One of list_fields; every section when absent"
    )


class GetCoverage(Arguments):
    craft_slug: str | None = Field(default=None, min_length=1, max_length=SLUG_MAX_CHARS)
    category_slug: str | None = Field(default=None, min_length=1, max_length=SLUG_MAX_CHARS)

    @model_validator(mode="after")
    def _one_subject(self) -> Self:
        if (self.craft_slug is None) == (self.category_slug is None):
            raise ValueError(ONE_SUBJECT)
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
        description=(
            "A slug from find_crafts; also brings the shared components of its concepts, compounds "
            "and districts"
        ),
    )
    field: Discipline | None = Field(default=None, description="One of list_fields")
    kind: PieceKind | None = Field(default=None, description="One kind of component")


async def _list_fields(context: ToolContext, arguments: ListFields) -> FieldList:
    if arguments.craft_slug is None:
        return knowledge_api.field_list()
    return await knowledge_api.held_field_list(context.session, arguments.craft_slug)


async def _find_crafts(context: ToolContext, arguments: FindCrafts) -> FoundCrafts:
    return await knowledge_api.found_crafts(
        context.session, context.index, arguments.query, site=context.site
    )


async def _get_facts(context: ToolContext, arguments: GetFacts) -> CraftFacts:
    return await knowledge_api.craft_facts(
        context.session,
        arguments.craft_slug,
        site=context.site,
        field=arguments.field,
        query=arguments.query,
        limit=arguments.limit,
    )


async def _get_section(context: ToolContext, arguments: GetSection) -> CraftSection:
    if arguments.field is None:
        return await knowledge_api.craft_sections(context.session, arguments.craft_slug, site=context.site)
    return await knowledge_api.craft_section(
        context.session, arguments.craft_slug, arguments.field, site=context.site
    )


async def _get_coverage(context: ToolContext, arguments: GetCoverage) -> SubjectCoverage:
    kind, slug = (
        (CRAFT, arguments.craft_slug) if arguments.craft_slug else (CATEGORY, arguments.category_slug)
    )
    return await coverage_reads.read_subject_coverage(context.session, kind, str(slug), site=context.site)


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
        "list_fields",
        "List the fields",
        "The 16 fields every fact and section is filed under, with what each covers and its chapter; "
        "with a craft_slug, each field also carries the craft's cited claims, sources, section and "
        "figures in it.",
        ListFields,
        FieldList,
        _list_fields,
    ),
    Tool(
        "find_crafts",
        "Find crafts",
        "Up to five crafts matching a name, a local name, a place or a kind, each with its slug, page "
        "and its cited claims per field: which fields are covered, thin or missing.",
        FindCrafts,
        FoundCrafts,
        _find_crafts,
    ),
    Tool(
        "get_facts",
        "Get a craft's facts",
        "The cited facts of one craft, optionally one field and ranked by words, each with its "
        "evidence level, verbatim quotes, locators, stored quantities and the figures resting on it; "
        "grouped by field with counts, and every field the craft holds too few facts in named as "
        "open work with its task key.",
        GetFacts,
        CraftFacts,
        _get_facts,
    ),
    Tool(
        "get_section",
        "Get a craft's sections",
        "The published prose of one craft's field, or of every field when none is named, each "
        "sentence with the facts it rests on, the sentence and fact counts per field, and each field "
        "still to research or write named as open work with its task key.",
        GetSection,
        CraftSection,
        _get_section,
    ),
    Tool(
        "get_coverage",
        "Get a page's field coverage",
        "For one craft, family or category, the cited claims, structure-cited claims, sources, "
        "published section and figures it holds in each of the 16 fields, which fields are covered, "
        "thin or missing, and the open field work with task keys to claim.",
        GetCoverage,
        SubjectCoverage,
        _get_coverage,
    ),
    Tool(
        "list_components",
        "Search the component library",
        "The registered interactive components (players, maps, molecules, charts), each with its "
        "label, title, description, kind, fields and the subjects it is keyed to. Search it before "
        "making or proposing a component: one keyed to a concept, compound or place is shared by "
        "every craft it applies to, so place it by its label rather than making another.",
        ListComponents,
        CraftComponents,
        _list_components,
    ),
)
