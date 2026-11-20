from __future__ import annotations

import re
import uuid
from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field
from typing import Any

from app.research.citations import SourceRef
from app.research.craft_chapters import Chapter, ChapterItem, FigureHead
from app.research.craft_page import CraftPage, PageClaim
from app.research.explainer import Block

from .document_components_parts import HYPOTHESIS, StructureText, hypothesis_texts, part_texts

__all__ = [
    "BLOCK_SEGMENT",
    "DRAWN_BLOCK_KINDS",
    "LEADING_PARTS",
    "DocumentStructure",
    "StructureBlock",
    "StructureItem",
    "StructureText",
    "block_citations",
    "block_label",
    "document_structure",
]

BLOCK_SEGMENT = "blocks"
SOURCES_CHAPTER = "sources"
DRAWN_BLOCK_KINDS = frozenset(
    {
        "process_ladder",
        "region_story",
        "reaction_player",
        "material_card",
        "molecule_3d",
        "seasons",
        "supply_map",
        "concept_graph",
        "climate_risk",
        "measure",
        "market_gi",
        "timeline_map",
        "zoom_story",
        "indigo_vat",
        "mordant_bath",
        "lost_wax",
        "firing",
    }
)
LEADING_PARTS = frozenset({"key_facts"})
LABEL_WORD = re.compile(r"[^a-z0-9]+")
SOURCE_KEY = "sourceId"
CLAIM_KEY = "claimId"


@dataclass(frozen=True)
class StructureBlock:
    label: str
    block: Block
    figure: FigureHead | None
    title: str
    description: str
    source_ids: tuple[str, ...] = ()
    claims: frozenset[uuid.UUID] = frozenset()

    def claim_ids(self) -> set[uuid.UUID]:
        return set(self.claims)

    def media_urls(self) -> set[str]:
        item = ChapterItem(block=self.block, part=None, figure=None, origin=None, piece_id=None)
        return {str(media.image_url) for media in item.shown_media()}


StructureItem = StructureText | StructureBlock


@dataclass(frozen=True)
class DocumentStructure:
    leading: Mapping[str, tuple[StructureItem, ...]] = field(default_factory=dict)
    trailing: Mapping[str, tuple[StructureItem, ...]] = field(default_factory=dict)
    sources: Mapping[str, SourceRef] = field(default_factory=dict)
    claims: tuple[PageClaim, ...] = ()

    def items(self) -> list[StructureItem]:
        return [item for found in (*self.leading.values(), *self.trailing.values()) for item in found]

    def claim_ids(self) -> set[uuid.UUID]:
        shown: set[uuid.UUID] = set()
        for item in self.items():
            shown |= item.claim_ids() if isinstance(item, StructureBlock) else set(item.claim_ids)
        return shown

    def media_urls(self) -> set[str]:
        return {url for item in self.items() if isinstance(item, StructureBlock) for url in item.media_urls()}


def block_citations(block: Block) -> tuple[tuple[str, ...], frozenset[uuid.UUID]]:
    found = list(_citations(block.model_dump(mode="json")))
    sources = dict.fromkeys([*(str(cite[SOURCE_KEY]) for cite in found), *block.cited_source_ids()])
    claims = {claim for cite in found if (claim := _uuid(cite[CLAIM_KEY])) is not None}
    return tuple(sources), frozenset(claims)


def _citations(node: Any) -> Iterator[dict[str, Any]]:
    if isinstance(node, dict):
        if SOURCE_KEY in node and CLAIM_KEY in node:
            yield node
        for value in node.values():
            yield from _citations(value)
    elif isinstance(node, list):
        for value in node:
            yield from _citations(value)


def _uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except ValueError:
        return None


def block_label(slug: str, block_id: str) -> str:
    return "/".join((slug.lower(), BLOCK_SEGMENT, LABEL_WORD.sub("-", block_id.lower()).strip("-")))


def document_structure(page: CraftPage, known: Mapping[str, SourceRef] | None = None) -> DocumentStructure:
    leading: dict[str, list[StructureItem]] = {}
    trailing: dict[str, list[StructureItem]] = {}
    taken: set[str] = set()
    sources = {**(known or {}), **{source.id: _ref(source) for source in page.sources}}
    fields = {claim.id: claim.discipline for claim in page.claims}
    for chapter in page.chapters:
        for item in chapter.items:
            if item.origin is not None:
                continue
            if item.part is not None:
                placed = leading if item.part.kind in LEADING_PARTS else trailing
                placed.setdefault(chapter.key, []).extend(part_texts(chapter.key, item.part, fields, taken))
                continue
            found = _block(page, chapter, item, sources, taken)
            if found is not None:
                trailing.setdefault(chapter.key, []).append(found)
    shown = DocumentStructure(trailing={key: tuple(items) for key, items in trailing.items()}).claim_ids()
    held = hypothesis_texts([c for c in page.claims if c.level == HYPOTHESIS and c.id not in shown], taken)
    if held:
        trailing.setdefault(SOURCES_CHAPTER, []).extend(held)
    return DocumentStructure(
        leading={key: tuple(items) for key, items in leading.items() if items},
        trailing={key: tuple(items) for key, items in trailing.items() if items},
        sources=sources,
        claims=tuple(page.claims),
    )


def _block(
    page: CraftPage,
    chapter: Chapter,
    item: ChapterItem,
    sources: Mapping[str, SourceRef],
    taken: set[str],
) -> StructureBlock | None:
    block = item.block
    if block is None or block.kind not in DRAWN_BLOCK_KINDS:
        return None
    source_ids, claims = block_citations(block)
    if any(source not in sources for source in source_ids):
        return None
    label = _unique(block_label(page.craft.slug, block.id), taken)
    title = item.figure.title if item.figure is not None else f"{chapter.title}: {page.craft.name}"
    return StructureBlock(
        label=label,
        block=block,
        figure=item.figure,
        title=title,
        description=f"{title}, drawn from the cited records of {page.craft.name}.",
        source_ids=source_ids,
        claims=claims,
    )


def _ref(source: SourceRef) -> SourceRef:
    return SourceRef.model_validate(source.model_dump(include=set(SourceRef.model_fields)))


def _unique(label: str, taken: set[str]) -> str:
    found, n = label, 1
    while found in taken:
        n += 1
        found = f"{label}-{n}"
    taken.add(found)
    return found
