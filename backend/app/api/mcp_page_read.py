from __future__ import annotations

from typing import Literal, Self

from pydantic import Field, model_validator

from app.core.errors import InvalidInput
from app.research.article_sections import ArticleSection
from app.research.base import ContractModel, absent, empty
from app.research.coverage import FieldCoverage
from app.research.knowledge_api import ATTRIBUTION, CraftSection, FieldInfo, FieldSection
from app.research.open_work import OpenTask
from app.research.page_layout import PageLayout
from app.research.page_proposals import PageSubject
from app.research.vocabulary import Discipline
from app.services import coverage_reads, knowledge_api
from app.services.open_work_subjects import WorkSubject, subject_by_key
from app.services.page_layouts import layout_of, subject_path

from .mcp_tool_base import Arguments, Tool, ToolContext

__all__ = ["GET_PAGE", "PAGE_PARTS", "GetPage", "PageRead"]

COVERAGE, SECTIONS, LAYOUT = PAGE_PARTS = ("coverage", "sections", "layout")
CATEGORY = "category"
NO_SECTIONS = "A category's page holds no section prose of its own; read its coverage and layout."
DESCRIPTION = (
    "Read one craft, family or category page in the parts you name. coverage: the cited claims, "
    "structure-cited claims, sources, published section and figures it holds in each of the sixteen fields, "
    "which are covered, thin or missing. sections: a craft's or family's published prose, one field or every "
    "field, each sentence with the facts it rests on. layout: where each text unit and component is placed "
    "(chapter, order, role, a picture's crop, size and caption), its version, and null where the page has "
    "none; a layout never holds a fact. Each part's open field work comes with its task key. With no subject "
    "it lists the sixteen fields, each with what it covers and its chapter."
)


class GetPage(Arguments):
    subject: PageSubject | None = Field(
        default=None,
        description="The page: kind craft, family or category and its slug from find_crafts; none lists the fields",
    )
    parts: list[Literal[*PAGE_PARTS]] | None = Field(
        default=None,
        min_length=1,
        max_length=len(PAGE_PARTS),
        description="Any of coverage, sections and layout; every part the page has when absent",
    )
    field: Discipline | None = Field(default=None, description="One field's section only")

    @model_validator(mode="after")
    def _parts_need_a_page(self) -> Self:
        if self.subject is None and (self.parts or self.field):
            raise ValueError("name the page as subject {kind, slug} to read its parts")
        return self


class PageRead(ContractModel):
    schema_version: Literal[1] = 1
    subject: PageSubject | None = Field(default=None, exclude_if=absent)
    parts: list[str] = Field(default_factory=list)
    fields: list[FieldInfo] = Field(default_factory=list, exclude_if=empty)
    coverage: FieldCoverage | None = Field(default=None, exclude_if=absent)
    field: Discipline | None = Field(default=None, exclude_if=absent)
    sections: list[ArticleSection] = Field(default_factory=list, exclude_if=empty)
    by_field: list[FieldSection] = Field(default_factory=list, exclude_if=empty)
    layout: PageLayout | None = None
    open_work: list[OpenTask] = Field(default_factory=list)
    page_url: str | None = Field(default=None, exclude_if=absent)
    attribution: str = ATTRIBUTION


async def _get_page(context: ToolContext, arguments: GetPage) -> PageRead:
    if arguments.subject is None:
        return PageRead(fields=knowledge_api.field_list().fields)
    subject = await subject_by_key(context.session, arguments.subject.kind, arguments.subject.slug)
    parts = _parts(arguments, subject)
    read: dict[str, object] = {
        "subject": PageSubject(kind=subject.kind, slug=subject.slug),
        "parts": parts,
        "page_url": f"{context.site}{subject_path(subject)}",
    }
    work: list[OpenTask] = []
    if COVERAGE in parts:
        held = await coverage_reads.read_subject_coverage(
            context.session, subject.kind, subject.slug, site=context.site
        )
        read["coverage"], work = held.coverage, [*work, *held.open_work]
    if SECTIONS in parts:
        section = await _sections(context, subject.slug, arguments.field)
        read |= {"field": section.field, "sections": _section_list(section), "by_field": section.by_field}
        work = [*work, *section.open_work]
    if LAYOUT in parts:
        read["layout"] = await layout_of(context.session, subject)
    return PageRead.model_validate({**read, "open_work": _once(work)})


def _parts(arguments: GetPage, subject: WorkSubject) -> list[str]:
    asked = list(dict.fromkeys(arguments.parts or ()))
    if subject.kind == CATEGORY and SECTIONS in asked:
        raise InvalidInput(NO_SECTIONS)
    if asked:
        return asked
    return [part for part in PAGE_PARTS if not (subject.kind == CATEGORY and part == SECTIONS)]


async def _sections(context: ToolContext, slug: str, field: str | None) -> CraftSection:
    if field is None:
        return await knowledge_api.craft_sections(context.session, slug, site=context.site)
    return await knowledge_api.craft_section(context.session, slug, field, site=context.site)


def _section_list(section: CraftSection) -> list[ArticleSection]:
    return [section.section] if section.section is not None else list(section.sections)


def _once(tasks: list[OpenTask]) -> list[OpenTask]:
    return list({task.key: task for task in tasks}.values())


GET_PAGE = Tool(
    "get_page",
    "Read a page",
    DESCRIPTION,
    GetPage,
    PageRead,
    _get_page,
    shows_output=True,
)
