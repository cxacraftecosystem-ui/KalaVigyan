from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.core.errors import InvalidInput
from app.research.chapter_keys import CHAPTER_KEYS
from app.research.coverage import FieldCoverage
from app.research.coverage_chapters import field_chapter
from app.research.monograph_document import MonographDocument
from app.research.monograph_page import CitedSource, ComponentEntry, LayoutEntry, MonographContent, TextUnit
from app.research.page_layout import PageLayout, arranged_layout, picture_label

from .component_proposals_drawn import drawn_delivery
from .document_components import DocumentStructure, StructureBlock
from .knowledge_view import ClaimView
from .monograph_generated_drawings import Drawings
from .monograph_generated_grids import StatedValue, fact_grid
from .monograph_generated_parts import RegisteredComponent, StoredSection
from .monograph_generated_pictures import PICTURE_KIND, PlateSource, plate_spec
from .monograph_generated_structure import CHAPTER_FIELDS, BlockSpecs, PlacedStructure, placed_structure
from .monograph_generated_units import (
    LEDE_FIELD,
    LEDE_SENTENCES,
    MASTHEAD_CHAPTER,
    SOURCES_CHAPTER,
    DraftUnit,
    SourceBook,
    SubjectRecord,
    chapter_heading,
    cited_unit,
    heading_unit,
    masthead_units,
    section_units,
)
from .page_layouts_backfill import LEADING_ROLES

__all__ = ["LAYOUT_DATA", "GeneratedParts", "assembled_document"]

LAYOUT_DATA = "page-layout"
HERO = "HERO"
CRAFT_SUBJECTS = frozenset({"craft", "family"})
DEFAULT_FIELD = "OVERVIEW"


@dataclass(frozen=True)
class GeneratedParts:
    subject_kind: str
    subject_slug: str
    page_url: str
    record: SubjectRecord
    sections: tuple[StoredSection, ...]
    visible: Mapping[uuid.UUID, ClaimView]
    sources: Mapping[str, CitedSource]
    components: tuple[RegisteredComponent, ...] = ()
    pictures: tuple[PlateSource, ...] = ()
    layout: PageLayout | None = None
    coverage: FieldCoverage | None = None
    values: Mapping[uuid.UUID, StatedValue] = field(default_factory=dict)
    structure: DocumentStructure | None = None


@dataclass
class _Page:
    units: dict[str, TextUnit] = field(default_factory=dict)
    drafts: dict[str, DraftUnit] = field(default_factory=dict)
    components: dict[str, ComponentEntry] = field(default_factory=dict)
    specs: dict[str, dict[str, Any]] = field(default_factory=dict)
    fragments: dict[str, str] = field(default_factory=dict)
    reused: dict[str, str] = field(default_factory=dict)
    borrowed_specs: dict[str, str] = field(default_factory=dict)
    default: list[LayoutEntry] = field(default_factory=list)
    held: dict[str, list[str]] = field(default_factory=dict)
    lede: list[str] = field(default_factory=list)
    hero: str | None = None
    blocks: dict[str, StructureBlock] = field(default_factory=dict)


def assembled_document(parts: GeneratedParts, drawings: Drawings) -> MonographDocument | None:
    page = _Page()
    texts = _texts(parts, page)
    if not page.drafts:
        return None
    placed = _structure(parts, page)
    pictures = _pictures(parts, page)
    components = _components(parts, page, drawings)
    _lay_out(page, (texts, pictures, components, placed.leading, placed.trailing))
    arranged = _headed(
        parts.record, page, [*_opening(parts, page), *arranged_layout(page.default, parts.layout)]
    )
    book = SourceBook()
    citations, claims = _cite(parts, page, arranged, book)
    _borrow(page, drawings, book, citations, claims)
    content = MonographContent(
        craft_slug=parts.subject_slug,
        sources=book.sources,
        citations=citations,
        citation_claims=claims,
        data={LAYOUT_DATA: parts.layout.model_dump(mode="json", by_alias=True)} if parts.layout else {},
        units=page.units,
        components=[page.components[e.ref] for e in arranged if e.kind == "component"],
        layout=arranged,
    )
    return MonographDocument(
        subject_kind=parts.subject_kind,
        subject_slug=parts.subject_slug,
        title=parts.record.name,
        version=sum(section.version for section in parts.sections),
        content=content,
        specs=page.specs,
        fragments=page.fragments,
        page_url=parts.page_url,
        coverage=parts.coverage,
    )


def _texts(parts: GeneratedParts, page: _Page) -> dict[str, list[str]]:
    taken: set[str] = set()
    named = {entry.ref for entry in parts.layout.entries} if parts.layout is not None else set()
    shown = parts.structure.claim_ids() if parts.structure is not None else set()
    by_chapter: dict[str, list[str]] = {}
    for section in parts.sections:
        drafts = section_units(section.field, section.sentences, parts.visible, taken)
        page.drafts.update((draft.unit_id, draft) for draft in drafts)
        if section.field == LEDE_FIELD and not page.lede:
            page.lede = [draft.unit_id for draft in drafts if draft.unit_id not in named][:LEDE_SENTENCES]
        body = [d for d in drafts if d.unit_id not in page.lede and not set(d.claim_ids) <= shown]
        if not body:
            continue
        refs = by_chapter.setdefault(field_chapter(section.field), [])
        refs.extend(_section_heading(section.field, parts.record, page))
        refs.extend(draft.unit_id for draft in body)
        refs.extend(_grid(body, parts, page))
    return by_chapter


def _grid(body: Sequence[DraftUnit], parts: GeneratedParts, page: _Page) -> tuple[str, ...]:
    grid = fact_grid(body, parts.values)
    page.units.update(grid.terms)
    page.drafts.update((draft.unit_id, draft) for draft in grid.values)
    return grid.refs


def _section_heading(field: str, record: SubjectRecord, page: _Page) -> list[str]:
    heading_id, heading = heading_unit(field)
    chapter = chapter_heading(heading.chapter, record)
    if chapter is not None and chapter[1].nodes == heading.nodes:
        return []
    page.units[heading_id] = heading
    return [heading_id]


def _structure(parts: GeneratedParts, page: _Page) -> PlacedStructure:
    placed = placed_structure(parts.structure, parts.visible, parts.subject_slug)
    page.drafts.update(placed.drafts)
    page.units.update(placed.units)
    page.components.update(placed.components)
    page.blocks.update(placed.blocks)
    return placed


def _pictures(parts: GeneratedParts, page: _Page) -> dict[str, list[str]]:
    by_chapter: dict[str, list[tuple[bool, str]]] = {}
    shown = parts.structure.media_urls() if parts.structure is not None else set()
    for source in parts.pictures:
        label = picture_label(parts.subject_slug, source.key)
        entry = parts.layout.entry(label) if parts.layout is not None else None
        role = entry.role if entry is not None else source.role
        if (role != HERO and source.src in shown) or not source.shown_with(parts.visible):
            continue
        plate = plate_spec(source, entry, len(page.held))
        if plate is None:
            continue
        if role == HERO and page.hero is None:
            page.hero = label
        page.components[label] = _picture_entry(parts, source, label)
        page.specs[label], held = plate
        page.units.update(held)
        page.held[label] = list(held)
        by_chapter.setdefault(source.chapter, []).append((role not in LEADING_ROLES, label))
    return {
        chapter: [label for _, label in sorted(found, key=lambda item: item[0])]
        for chapter, found in by_chapter.items()
    }


def _components(parts: GeneratedParts, page: _Page, drawings: Drawings) -> dict[str, list[str]]:
    by_chapter: dict[str, list[str]] = {}
    for component in parts.components:
        if component.label in page.components or not _drawn(parts, page, drawings, component):
            continue
        chapter = field_chapter(component.field)
        page.components[component.label] = ComponentEntry(
            label=component.label,
            chapter=chapter,
            anchor=component.anchor or _anchor(component.label),
            kind=component.kind,
            title=component.title,
            description=component.description,
            field=component.field,
            fields=list(component.fields),
            subjects=list(component.subjects),
        )
        by_chapter.setdefault(chapter, []).append(component.label)
    return by_chapter


def _drawn(parts: GeneratedParts, page: _Page, drawings: Drawings, component: RegisteredComponent) -> bool:
    if component.delivered is not None:
        place = (field_chapter(component.field), component.field)
        taken = {*page.units, *page.drafts}
        drawn = drawn_delivery(component.delivered, place=place, visible=parts.visible, taken=taken)
        if drawn is None:
            return False
        page.specs[component.label] = drawn.spec
        page.drafts.update(drawn.drafts)
        page.held[component.label] = list(drawn.drafts)
        return True
    if component.monograph is None:
        return False
    spec = drawings.spec(component.monograph, component.label)
    if spec is not None:
        page.specs[component.label] = spec
        page.borrowed_specs[component.label] = component.monograph
    elif drawings.has_fragment(component.monograph, component.label):
        page.reused[component.label] = component.monograph
    else:
        return False
    return True


def _borrow(
    page: _Page, drawings: Drawings, book: SourceBook, citations: dict[str, Any], claims: dict[str, list[str]]
) -> None:
    for label, monograph in page.reused.items():
        filled = drawings.fragment(monograph, label, book)
        page.fragments[label] = filled.markup
        citations.update(filled.citations)
        claims.update(filled.citation_claims)
    for label, monograph in page.borrowed_specs.items():
        named = drawings.spec_units(monograph, page.specs[label], book)
        for key, unit in named.units.items():
            if page.units.get(key, unit) != unit:
                raise InvalidInput(f"The spec of {label} names unit {key}, which this page already holds")
            page.units[key] = unit
        citations.update(named.citations)
        claims.update(named.citation_claims)


def _lay_out(page: _Page, found: Sequence[Mapping[str, list[str]]]) -> None:
    texts, pictures, components, leading, trailing = found
    chapters = dict.fromkeys([*CHAPTER_KEYS, *pictures, *leading, *texts, *trailing, *components])
    for chapter in chapters:
        refs = [
            *(ref for ref in pictures.get(chapter, []) if ref != page.hero),
            *leading.get(chapter, []),
            *texts.get(chapter, []),
            *trailing.get(chapter, []),
            *components.get(chapter, []),
        ]
        page.default += [e for ref in refs for e in _entry(chapter, ref, None, page)]


def _opening(parts: GeneratedParts, page: _Page) -> list[LayoutEntry]:
    masthead = masthead_units(parts.record)
    page.units.update(masthead)
    heads = [page.hero] if page.hero is not None else []
    return [e for ref in (*heads, *masthead, *page.lede) for e in _entry(MASTHEAD_CHAPTER, ref, None, page)]


def _headed(record: SubjectRecord, page: _Page, arranged: Sequence[LayoutEntry]) -> list[LayoutEntry]:
    headed: list[LayoutEntry] = []
    seen = {MASTHEAD_CHAPTER}
    for entry in arranged:
        if entry.chapter not in seen:
            seen.add(entry.chapter)
            headed.extend(_chapter_head(entry.chapter, record, page))
        headed.append(entry)
    if SOURCES_CHAPTER not in seen:
        headed.extend(_chapter_head(SOURCES_CHAPTER, record, page))
    return headed


def _chapter_head(chapter: str, record: SubjectRecord, page: _Page) -> list[LayoutEntry]:
    heading = chapter_heading(chapter, record)
    if heading is None:
        return []
    ref, unit = heading
    page.units[ref] = unit
    return [LayoutEntry(chapter=chapter, kind="unit", ref=ref, within=None)]


def _entry(chapter: str, ref: str, within: str | None, page: _Page) -> list[LayoutEntry]:
    kind = "component" if ref in page.components else "unit"
    placed = LayoutEntry(chapter=chapter, kind=kind, ref=ref, within=within)
    return [
        placed,
        *(LayoutEntry(chapter=chapter, kind="unit", ref=unit, within=ref) for unit in page.held.get(ref, [])),
    ]


def _cite(
    parts: GeneratedParts, page: _Page, arranged: Sequence[LayoutEntry], book: SourceBook
) -> tuple[dict[str, Any], dict[str, list[str]]]:
    citations: dict[str, Any] = {}
    claims: dict[str, list[str]] = {}
    specs = BlockSpecs(parts.structure.sources if parts.structure is not None else {})
    for entry in arranged:
        if entry.kind == "component":
            settled = page.components[entry.ref].model_copy(update={"chapter": entry.chapter})
            page.components[entry.ref] = settled
            if entry.ref in page.blocks:
                page.specs[entry.ref] = specs.spec(page.blocks[entry.ref], book)
            continue
        draft = page.drafts.get(entry.ref)
        if draft is None:
            page.units[entry.ref] = page.units[entry.ref].model_copy(update={"chapter": entry.chapter})
            continue
        unit, quotes = cited_unit(draft, parts.visible, book, parts.sources)
        page.units[entry.ref] = unit.model_copy(update={"chapter": entry.chapter})
        if quotes:
            citations[entry.ref] = quotes
            claims[entry.ref] = list(unit.claim_ids)
    return citations, claims


def _picture_entry(parts: GeneratedParts, source: PlateSource, label: str) -> ComponentEntry:
    return ComponentEntry(
        label=label,
        chapter=source.chapter,
        anchor=_anchor(label),
        kind=PICTURE_KIND,
        title=source.caption,
        description=f"A picture for {parts.record.name}: {source.caption}"
        + (f" ({source.attribution})." if source.attribution else "."),
        field=CHAPTER_FIELDS.get(source.chapter, DEFAULT_FIELD),
        fields=[],
        subjects=[f"craft:{parts.subject_slug}"] if parts.subject_kind in CRAFT_SUBJECTS else [],
    )


def _anchor(label: str) -> str:
    return "#" + label.replace("/", "--")
