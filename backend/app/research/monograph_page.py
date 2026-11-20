from __future__ import annotations

import html
import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from functools import partial
from types import MappingProxyType
from typing import Any, Literal

from pydantic import Field

from app.core.errors import InvalidInput
from app.models.component_kinds import DOCUMENT_KINDS

from .base import ContractModel
from .vocabulary import Discipline, PieceKind

__all__ = [
    "COMPONENT_SLOT",
    "DATA_SLOT",
    "KIT_FILES",
    "KIT_SLOT",
    "MONOGRAPH_SCHEMA_VERSION",
    "NO_PARTS",
    "SLOT_PATTERN",
    "UNIT_SLOT",
    "CitedSource",
    "ComponentEntry",
    "LayoutEntry",
    "MonographContent",
    "PageParts",
    "Quote",
    "TextUnit",
    "assemble_template",
    "authored_main",
    "keyed_kit",
    "kit_parts",
    "kit_slot_key",
    "kit_source",
    "render_fragment",
    "render_nodes",
    "render_page",
    "served_kit",
    "slot",
    "slot_keys",
]

MONOGRAPH_SCHEMA_VERSION = 1
COMPONENT_LABEL_PATTERN = r"^[a-z0-9]+(-[a-z0-9]+)*(/[a-z0-9]+(-[a-z0-9]+)*){2,}$"
SLOT_PATTERN = re.compile(r'<kv-slot (unit|data|component|kit)="([A-Za-z0-9._/#-]+)"></kv-slot>')
UNIT_SLOT = "unit"
DATA_SLOT = "data"
COMPONENT_SLOT = "component"
MAIN_OPEN = '<main id="kv-main">'
MAIN_CLOSE = "</main>"
KIT_SLOT = "kit"
KIT_FILES = ("monograph.css", "monograph.js")
KIT_PART_MARKERS = MappingProxyType({".css": "@kv-part {name};\n", ".js": '"kv-part {name}";\n'})
KIT_PART_NAME = "[a-z0-9]+(?:-[a-z0-9]+)*"
KIT_PART_END = "\n"
KIT_KEY_SEPARATOR = "#"
CITES_DATA = "kv-cites"
ITALIC_ROLES = ("loc", "bot", "ring", "on")
MARK_TAGS = {"b": "b", "sub": "sub", "sup": "sup", "mark": "mark"}
SENTENCE_ATTRS = (("src", "data-src"), ("sid", "data-sid"), ("pair", "data-pair"))
LINK_ATTRS = (("rel", "rel"), ("target", "target"), ("ask", "data-ask"), ("lang", "lang"))

Node = str | dict[str, Any]


class CitedSource(ContractModel):
    number: int = Field(ge=1)
    title: str
    full_title: str | None
    publisher: str | None
    year: int | None
    grade: str | None
    url: str | None
    extra: str | None
    dossier_source_id: str | None


class Quote(ContractModel):
    source: str
    locator: str | None
    quote: str | None


class TextUnit(ContractModel):
    chapter: str
    tag: str
    field: Discipline | None
    nodes: list[Any]
    claim_ids: list[str]


class ComponentEntry(ContractModel):
    label: str = Field(pattern=COMPONENT_LABEL_PATTERN)
    chapter: str
    anchor: str
    kind: PieceKind | Literal[*DOCUMENT_KINDS]
    title: str
    description: str
    field: Discipline
    fields: list[Discipline]
    subjects: list[str]


class LayoutEntry(ContractModel):
    chapter: str
    kind: Literal["unit", "component"]
    ref: str
    within: str | None = None


class MonographContent(ContractModel):
    schema_version: Literal[1] = MONOGRAPH_SCHEMA_VERSION
    craft_slug: str
    sources: dict[str, CitedSource]
    citations: dict[str, list[Quote]]
    citation_claims: dict[str, list[str]]
    data: dict[str, Any]
    units: dict[str, TextUnit]
    components: list[ComponentEntry]
    layout: list[LayoutEntry]


NOTHING: Mapping[str, str] = MappingProxyType({})


@dataclass(frozen=True)
class PageParts:
    fragments: Mapping[str, str] = NOTHING
    kit: Mapping[str, str] = NOTHING


NO_PARTS = PageParts()
SlotFill = Callable[[str], str]


def slot(kind: str, key: str) -> str:
    return f'<kv-slot {kind}="{key}"></kv-slot>'


def slot_keys(text: str, kind: str) -> list[str]:
    return [key for found, key in SLOT_PATTERN.findall(text) if found == kind]


def render_page(template: str, content: MonographContent, *, parts: PageParts = NO_PARTS) -> str:
    fills = {
        UNIT_SLOT: partial(_unit, content),
        DATA_SLOT: partial(_data, content=content),
        KIT_SLOT: partial(_kit_part, parts.kit),
    }
    return _filled(_with_components(template, parts.fragments), fills)


def authored_main(
    shell: str, content: MonographContent, fragments: Mapping[str, str], *, kept: frozenset[str] = frozenset()
) -> str:
    fills = {UNIT_SLOT: partial(_unit, content), DATA_SLOT: partial(_data, content=content)}
    page = _filled(_with_components(shell, fragments, kept=kept), fills)
    start = page.find(MAIN_OPEN)
    end = page.rfind(MAIN_CLOSE)
    if start < 0 or end < start:
        raise InvalidInput("The shell has no main element")
    return page[start + len(MAIN_OPEN) : end]


def render_fragment(fragment: str, content: MonographContent) -> str:
    fills = {
        UNIT_SLOT: partial(_unit, content),
        DATA_SLOT: partial(_data, content=content),
        KIT_SLOT: _kit_refused,
    }
    return _filled(fragment, fills)


def assemble_template(shell: str, parts: PageParts) -> str:
    return _filled(_with_components(shell, parts.fragments), {KIT_SLOT: partial(_kit_part, parts.kit)})


def kit_slot_key(file_name: str, part: str) -> str:
    return f"{file_name}{KIT_KEY_SEPARATOR}{part}"


def kit_parts(source: str, *, file_name: str) -> dict[str, str]:
    marker = _kit_marker(file_name)
    found = list(marker.finditer(source))
    if not found or found[0].start() != 0:
        raise InvalidInput(f"The kit file {file_name} does not open with a part marker")
    ends = [match.start() for match in found[1:]] + [len(source)]
    parts: dict[str, str] = {}
    for match, end in zip(found, ends, strict=True):
        name, text = match.group("name"), source[match.end() : end]
        if name in parts:
            raise InvalidInput(f"The kit file {file_name} names the part {name} twice")
        if not text.endswith(KIT_PART_END):
            raise InvalidInput(f"The kit part {name} of {file_name} does not end with its newline")
        parts[name] = text.removesuffix(KIT_PART_END)
    return parts


def kit_source(parts: Mapping[str, str], *, file_name: str) -> str:
    template = KIT_PART_MARKERS[_kit_suffix(file_name)]
    marker = _kit_marker(file_name)
    held = [name for name, text in parts.items() if marker.search(text)]
    if held:
        raise InvalidInput(f"These kit parts of {file_name} hold a part marker: {held}")
    return "".join(template.format(name=name) + text + KIT_PART_END for name, text in parts.items())


def served_kit(source: str, *, file_name: str) -> str:
    return "".join(kit_parts(source, file_name=file_name).values())


def keyed_kit(sources: Mapping[str, str]) -> dict[str, str]:
    return {
        kit_slot_key(file_name, part): text
        for file_name, source in sources.items()
        for part, text in kit_parts(source, file_name=file_name).items()
    }


def _filled(text: str, fills: Mapping[str, SlotFill]) -> str:
    def fill(found: re.Match[str]) -> str:
        chosen = fills.get(found.group(1))
        return found.group(0) if chosen is None else chosen(found.group(2))

    return SLOT_PATTERN.sub(fill, text)


def _with_components(
    text: str, fragments: Mapping[str, str], held: tuple[str, ...] = (), *, kept: frozenset[str] = frozenset()
) -> str:
    def fill(found: re.Match[str]) -> str:
        if found.group(1) != COMPONENT_SLOT or found.group(2) in kept:
            return found.group(0)
        label = found.group(2)
        if label in held:
            raise InvalidInput(f"The fragment of component {label} holds its own slot")
        fragment = fragments.get(label)
        if fragment is None:
            raise InvalidInput(f"The template has a slot for component {label}, which has no fragment")
        return _with_components(fragment, fragments, (*held, label), kept=kept)

    return SLOT_PATTERN.sub(fill, text)


def _unit(content: MonographContent, key: str) -> str:
    unit = content.units.get(key)
    if unit is None:
        raise InvalidInput(f"The template has a slot for unit {key}, which the content lacks")
    return render_nodes(unit.nodes, content.sources)


def _kit_part(kit: Mapping[str, str], key: str) -> str:
    part = kit.get(key)
    if part is None:
        raise InvalidInput(f"The template has a slot for the kit part {key}, which the kit lacks")
    return part


def _kit_refused(key: str) -> str:
    raise InvalidInput(f"A component's fragment holds the kit slot {key}; the kit is page-wide")


def _kit_suffix(file_name: str) -> str:
    suffix = file_name[file_name.rfind(".") :]
    if suffix not in KIT_PART_MARKERS:
        raise InvalidInput(f"No kit part marker for {file_name}")
    return suffix


def _kit_marker(file_name: str) -> re.Pattern[str]:
    template = re.escape(KIT_PART_MARKERS[_kit_suffix(file_name)])
    return re.compile("^" + template.replace(re.escape("{name}"), f"(?P<name>{KIT_PART_NAME})"), re.M)


def render_nodes(nodes: Sequence[Node], sources: Mapping[str, CitedSource]) -> str:
    return "".join(_node(node, sources) for node in nodes)


def _node(node: Node, sources: Mapping[str, CitedSource]) -> str:
    if isinstance(node, str):
        return html.escape(node, quote=False)
    mark = node.get("m")
    inner = render_nodes(node.get("c", []), sources)
    if mark == "s":
        extra = f" {node['cls']}" if node.get("cls") else ""
        return f'<span class="s{extra}"{_attrs(node, SENTENCE_ATTRS)}>{inner}</span>'
    if mark == "span":
        return (
            f'<span class="{html.escape(node["cls"])}">{inner}</span>'
            if node.get("cls")
            else f"<span>{inner}</span>"
        )
    if mark == "cite":
        return f'<span class="nw">{inner}{_cite_button(node, sources)}</span>'
    if mark == "i":
        role = node.get("role")
        if role is not None and role not in ITALIC_ROLES:
            raise InvalidInput(f"No italic role {role!r}")
        return f'<i class="{role}">{inner}</i>' if role else f"<i>{inner}</i>"
    if mark in MARK_TAGS:
        tag = MARK_TAGS[mark]
        return f"<{tag}>{inner}</{tag}>"
    if mark == "link":
        if node.get("cls"):
            return f'<a class="{html.escape(node["cls"])}" href="{html.escape(node["href"])}">{inner}</a>'
        return f'<a href="{html.escape(node["href"])}"{_attrs(node, LINK_ATTRS)}>{inner}</a>'
    if mark == "figref":
        return f'<span class="kv-figref" data-figref="{html.escape(node["ref"])}">{inner}</span>'
    raise InvalidInput(f"No inline mark {mark!r}")


def _attrs(node: Mapping[str, Any], names: Sequence[tuple[str, str]]) -> str:
    return "".join(
        f' {attribute}="{html.escape(node[key])}"' for key, attribute in names if node.get(key) is not None
    )


def _cite_button(node: Mapping[str, Any], sources: Mapping[str, CitedSource]) -> str:
    keys = list(node["g"])
    missing = [key for key in keys if key not in sources]
    if missing:
        raise InvalidInput(f"Citation {node['key']} names unknown sources {missing}")
    shown = sorted({sources[key].number: sources[key] for key in keys}.items())
    numbers = [str(number) for number, _ in shown]
    label = f"Source {numbers[0]}" if len(numbers) == 1 else f"Sources {', '.join(numbers)}"
    described = "; ".join(source.title for _, source in shown)
    return (
        f'<button class="kcite" type="button" data-c="{html.escape(node["key"])}" '
        f'data-g="{" ".join(keys)}" aria-haspopup="dialog" aria-expanded="false" '
        f'aria-label="{label}" aria-description="{html.escape(described)}">{",".join(numbers)}</button>'
    )


def _data(key: str, content: MonographContent) -> str:
    if key == CITES_DATA:
        value: Any = {
            "s": {
                g: [
                    s.number,
                    s.title,
                    s.full_title,
                    s.publisher,
                    s.year,
                    s.grade,
                    s.url,
                    s.extra,
                ]
                for g, s in content.sources.items()
            },
            "c": {
                key: [[q.source, q.locator, q.quote] for q in quotes]
                for key, quotes in content.citations.items()
            },
        }
    elif key in content.data:
        value = content.data[key]
    else:
        raise InvalidInput(f"The template has a slot for data {key}, which the content lacks")
    return json.dumps(value, ensure_ascii=False).replace("</", "<\\/")
