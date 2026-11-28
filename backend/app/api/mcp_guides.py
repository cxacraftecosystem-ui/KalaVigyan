from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from functools import cache, partial
from pathlib import PurePosixPath
from types import MappingProxyType
from typing import Any

from pydantic import ConfigDict, Field

from app.core.errors import InvalidInput
from app.data.guide_pages import PAGE_BYTES, guide_title, paged
from app.data.skill_library import INDEX_URI
from app.research.bar_references import KIT_GUIDES, worked_topic
from app.research.base import ContractModel
from app.research.page_counts import BAR_SLUG, Counts, chapter_order, content_counts, total_counts
from app.services.bar_references import kit_text, worked_chapters, worked_text
from app.services.layer_guide import MAP_LAYERS_TOPIC, map_layers_text
from app.services.page_layouts import page_path
from app.services.page_report import bar_content

from .mcp_protocol import RESOURCE_NOT_FOUND, RequestError
from .mcp_resources import RESOURCES

__all__ = [
    "ADDRESS_PATTERN",
    "BAR",
    "CONTENTS",
    "CONTENTS_ADDRESS",
    "GUIDES",
    "GUIDE_PREFIX",
    "GUIDE_TEMPLATE",
    "Guide",
    "GuideSheet",
    "bar_text",
    "contents_text",
    "guide_read",
    "guide_sheet",
    "guide_sheets",
    "guide_template",
    "is_guide_uri",
    "sheet_holding",
    "sheet_matching",
]

GUIDE_PREFIX = "kalavigyan://guides/"
GUIDE_TEMPLATE = GUIDE_PREFIX + "{topic}/{page}"
ADDRESS_PATTERN = r"^[a-z0-9-]{1,60}/[1-9][0-9]{0,3}$"
ADDRESS = re.compile(ADDRESS_PATTERN)
MARKDOWN = "text/markdown"
SKILL_ENTRY = "SKILL"
BAR, CONTENTS = "bar", "contents"
FIRST_PAGE = 1
CONTENTS_ADDRESS = f"{CONTENTS}/{FIRST_PAGE}"
NO_TOPIC = "No guide is named {topic}; {contents} lists every guide and its pages."
NO_PAGE = "The guide {topic} has pages 1 to {pages}, not {page}."
NOT_A_PAGE = "A guide page is kalavigyan://guides/<topic>/<page>, such as kalavigyan://guides/{contents}."
CONTENTS_HEAD = (
    "# Every page of the guide\n\n"
    "Every guide the KalaVigyan MCP server serves, in numbered pages of at most {size:,} bytes: the references, "
    "the skills, the design system, the design pages, the contracts, the Kutch Ajrakh bar, Ajrakh's chapters "
    "worked through and the kit they are drawn with. Read a page with `get_page` and "
    "`guide` set to its address, or as the resource `kalavigyan://guides/<topic>/<page>`. The tools hand you "
    "the page for the step you are on, and every page names the next.\n"
)
BAR_HEAD = (
    "# The bar: Kutch Ajrakh\n\n"
    "Kutch Ajrakh's page is the one the owner approved, and every page built over MCP is set beside it. Read it "
    "with `get_page` and subject {{kind craft, slug {slug}}}; the site draws it at `{path}`. It holds "
    "{pictures} pictures and {figures} figures, {interactives} of them interactives and {maps} maps, chapter by "
    "chapter:\n\n"
    "| Chapter | Pictures | Figures | Interactives | Maps |\n"
    "|---|---|---|---|---|\n"
)
BAR_CLOSE = (
    "\nThe preview's report sets a page beside these counts chapter by chapter, a mirror and never a target: a "
    "page holds the figures its own craft's facts call for, and the page checklist's rules pass or fail it. "
    "Kutch Ajrakh is the worked example of the thinking the page playbook (`playbook/1`) teaches, each of its "
    "chapters served worked through, every component with its kind, its spec, its place and the sentences "
    "around it: {worked}.\n"
)
TEMPLATE_DESCRIPTION = (
    "One numbered page, of at most {size:,} bytes, of a guide the server serves: a reference, a skill, a design "
    "page or a contract by its file's name (playbook, cookbook, page-checklist, components, drawing, open-work, "
    "kalavigyan-contributor, kalavigyan-design, system), the Kutch Ajrakh bar (bar), one of Ajrakh's chapters "
    "worked through (ajrakh-chemistry), the kit (kit-stylesheet, kit-script), the map layers with their "
    "dataset records (map-layers) or the list of every page "
    "({contents}). Each page names where it sits and the next."
)


@dataclass(frozen=True)
class Guide:
    topic: str
    whole: str
    text: Callable[[], str]


class GuideSheet(ContractModel):
    model_config = ConfigDict(str_strip_whitespace=False)

    address: str
    title: str
    page: int = Field(ge=1)
    pages: int = Field(ge=1)
    sections: list[str]
    next: str | None
    whole: str
    text: str

    @property
    def uri(self) -> str:
        return GUIDE_PREFIX + self.address

    def where(self) -> str:
        held = "; ".join(self.sections) or self.title
        following = f"Next: {self.next}." if self.next else "Its last page."
        return (
            f"> {self.title}, page {self.page} of {self.pages} ({self.address}): {held}. {following} "
            f"Whole: {self.whole}."
        )

    def served(self) -> str:
        return f"{self.where()}\n\n{self.text}"


def bar_text() -> str:
    content = bar_content()
    counted = content_counts(content)
    rows = [(key, counted.get(key, Counts())) for key in dict.fromkeys([*chapter_order(content), *counted])]
    total = total_counts(counted.values())
    head = BAR_HEAD.format(slug=BAR_SLUG, path=page_path("craft", BAR_SLUG), **total.model_dump())
    lines = [_row(chapter, counts) for chapter, counts in rows]
    worked = ", ".join(f"`{worked_topic(chapter)}/{FIRST_PAGE}`" for chapter in worked_chapters())
    return head + "\n".join([*lines, _row("All", total)]) + "\n" + BAR_CLOSE.format(worked=worked)


def contents_text() -> str:
    parts = [CONTENTS_HEAD.format(size=PAGE_BYTES)]
    for topic in GUIDES:
        if topic == CONTENTS:
            continue
        sheets = guide_sheets(topic)
        count = len(sheets)
        listed = "\n".join(
            f"- `{sheet.address}`: {'; '.join(sheet.sections) or sheet.title}" for sheet in sheets
        )
        parts.append(
            f"## {sheets[0].title} (`{topic}`, {count} page{'' if count == 1 else 's'})\n\n{listed}\n"
        )
    return "\n".join(parts)


def _row(chapter: str, counts: Counts) -> str:
    return f"| {chapter} | {counts.pictures} | {counts.figures} | {counts.interactives} | {counts.maps} |"


def _topic(uri: str) -> str:
    path = PurePosixPath(uri.split("://", 1)[1])
    return path.parent.name if path.stem == SKILL_ENTRY else path.stem.lower()


def _made(topic: str, text: Callable[[], str]) -> Guide:
    return Guide(topic, f"{GUIDE_PREFIX}{topic}/{FIRST_PAGE}", text)


def _registry() -> Mapping[str, Guide]:
    served = [
        Guide(_topic(uri), uri, resource.text)
        for uri, resource in RESOURCES.items()
        if resource.mime_type == MARKDOWN and uri != INDEX_URI
    ]
    made = [
        Guide(BAR, f"{GUIDE_PREFIX}{BAR}/{FIRST_PAGE}", bar_text),
        Guide(CONTENTS, GUIDE_PREFIX + CONTENTS_ADDRESS, contents_text),
        _made(MAP_LAYERS_TOPIC, map_layers_text),
        *(_made(worked_topic(chapter), partial(worked_text, chapter)) for chapter in worked_chapters()),
        *(_made(topic, partial(kit_text, topic)) for topic in KIT_GUIDES),
    ]
    found: dict[str, Guide] = {}
    for guide in (*served, *made):
        if guide.topic in found:
            raise ValueError(
                f"two guides are named {guide.topic}: {found[guide.topic].whole} and {guide.whole}"
            )
        found[guide.topic] = guide
    return MappingProxyType(found)


GUIDES: Mapping[str, Guide] = _registry()


@cache
def guide_sheets(topic: str) -> tuple[GuideSheet, ...]:
    guide = GUIDES.get(topic)
    if guide is None:
        raise InvalidInput(NO_TOPIC.format(topic=topic, contents=CONTENTS_ADDRESS))
    text = guide.text()
    title = guide_title(text) or topic
    pages = paged(text)
    count = len(pages)
    return tuple(
        GuideSheet(
            address=f"{topic}/{number}",
            title=title,
            page=number,
            pages=count,
            sections=list(page.sections),
            next=f"{topic}/{number + 1}" if number < count else None,
            whole=guide.whole,
            text=page.body,
        )
        for number, page in enumerate(pages, start=FIRST_PAGE)
    )


def guide_sheet(address: str) -> GuideSheet:
    topic, _, page = address.partition("/")
    sheets = guide_sheets(topic)
    if not page.isdigit() or not FIRST_PAGE <= int(page) <= len(sheets):
        raise InvalidInput(NO_PAGE.format(topic=topic, pages=len(sheets), page=page))
    return sheets[int(page) - FIRST_PAGE]


def sheet_holding(topic: str, section: str) -> GuideSheet:
    for sheet in guide_sheets(topic):
        if section in sheet.sections:
            return sheet
    raise LookupError(f"the guide {topic} has no section {section!r}")


def sheet_matching(topic: str, pattern: re.Pattern[str]) -> GuideSheet:
    for sheet in guide_sheets(topic):
        if pattern.search(sheet.text):
            return sheet
    raise LookupError(f"no page of the guide {topic} holds {pattern.pattern!r}")


def is_guide_uri(uri: Any) -> bool:
    return isinstance(uri, str) and uri.startswith(GUIDE_PREFIX)


def guide_template() -> dict[str, Any]:
    return {
        "uriTemplate": GUIDE_TEMPLATE,
        "name": "kalavigyan-guide-page",
        "title": "A page of a KalaVigyan guide",
        "description": TEMPLATE_DESCRIPTION.format(size=PAGE_BYTES, contents=CONTENTS_ADDRESS),
        "mimeType": MARKDOWN,
    }


def guide_read(uri: str) -> dict[str, Any]:
    address = uri.removeprefix(GUIDE_PREFIX)
    if ADDRESS.match(address) is None:
        raise RequestError(RESOURCE_NOT_FOUND, NOT_A_PAGE.format(contents=CONTENTS_ADDRESS))
    try:
        sheet = guide_sheet(address)
    except InvalidInput as missing:
        raise RequestError(RESOURCE_NOT_FOUND, str(missing)) from None
    return {"contents": [{"uri": uri, "mimeType": MARKDOWN, "text": sheet.served()}]}
