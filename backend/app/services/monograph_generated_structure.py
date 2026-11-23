from __future__ import annotations

import uuid
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any

from app.models.enums import DISCIPLINES
from app.research.chapter_keys import CHAPTER_KEYS, DISCIPLINE_CHAPTERS
from app.research.citations import SourceRef
from app.research.component_specs import checked_spec
from app.research.component_specs_blocks import ANSWER_BLOCK_KIND
from app.research.monograph_page import ComponentEntry, TextUnit

from .document_components import DocumentStructure, StructureBlock, StructureItem
from .document_components_parts import HEADING_TAG, HYPOTHESIS, StructureText
from .knowledge_view import ClaimView
from .monograph_generated_parts import StoredSection
from .monograph_generated_units import DraftUnit, SourceBook, stored_source

__all__ = [
    "CHAPTER_FIELDS",
    "BlockSpecs",
    "PlacedStructure",
    "placed_structure",
    "shown_claim_ids",
    "structure_claim_ids",
    "with_page_claims",
]

DEFAULT_FIELD = "OVERVIEW"
CHAPTER_FIELDS: Mapping[str, str] = MappingProxyType(
    {
        chapter: next((f for f, c in DISCIPLINE_CHAPTERS.items() if c == chapter), DEFAULT_FIELD)
        for chapter in CHAPTER_KEYS
    }
)
FIELD_ORDER = {discipline: n for n, discipline in enumerate(DISCIPLINES)}
CRAFT_SUBJECT = "craft:{slug}"


@dataclass
class PlacedStructure:
    leading: dict[str, list[str]] = field(default_factory=dict)
    trailing: dict[str, list[str]] = field(default_factory=dict)
    drafts: dict[str, DraftUnit] = field(default_factory=dict)
    units: dict[str, TextUnit] = field(default_factory=dict)
    components: dict[str, ComponentEntry] = field(default_factory=dict)
    blocks: dict[str, StructureBlock] = field(default_factory=dict)


@dataclass
class BlockSpecs:
    sources: Mapping[str, SourceRef]
    counts: dict[str, int] = field(default_factory=dict)

    def spec(self, item: StructureBlock, book: SourceBook) -> dict[str, Any]:
        figure = None
        if item.figure is not None:
            number = self.counts.get(item.figure.kind, 0) + 1
            self.counts[item.figure.kind] = number
            figure = {"kind": item.figure.kind, "number": number, "title": item.figure.title}
        listed = []
        for source_id in item.source_ids:
            ref = self.sources[source_id].model_dump(mode="json")
            listed.append({"key": book.key(stored_source(ref)), "ref": ref})
        spec = {"block": item.block.model_dump(mode="json"), "figure": figure, "sources": listed}
        return checked_spec(ANSWER_BLOCK_KIND, spec).model_dump(mode="json")


def shown_claim_ids(sections: Sequence[StoredSection], structure: DocumentStructure | None) -> set[uuid.UUID]:
    shown = {uuid.UUID(str(c)) for s in sections for sentence in s.sentences for c in sentence["claimIds"]}
    if structure is not None:
        shown |= structure.claim_ids()
    return shown


def with_page_claims(
    sections: Sequence[StoredSection],
    structure: DocumentStructure | None,
    *,
    listed: Collection[uuid.UUID] = frozenset(),
) -> list[StoredSection]:
    if structure is None:
        return list(sections)
    shown = shown_claim_ids(sections, structure) | set(listed)
    extra: dict[str, list[dict[str, Any]]] = {}
    for claim in structure.claims:
        if claim.level == HYPOTHESIS or claim.id in shown:
            continue
        shown.add(claim.id)
        extra.setdefault(claim.discipline, []).append({"text": claim.text, "claimIds": [str(claim.id)]})
    merged = {section.field: section for section in sections}
    for discipline, sentences in extra.items():
        found = merged.get(discipline)
        before = found.sentences if found is not None else ()
        merged[discipline] = StoredSection(discipline, found.version if found else 0, (*before, *sentences))
    return sorted(merged.values(), key=lambda section: FIELD_ORDER.get(section.field, len(FIELD_ORDER)))


def structure_claim_ids(structure: DocumentStructure | None) -> list[uuid.UUID]:
    if structure is None:
        return []
    return [
        claim for item in structure.items() if isinstance(item, StructureText) for claim in item.claim_ids
    ]


def placed_structure(
    structure: DocumentStructure | None, visible: Mapping[uuid.UUID, ClaimView], subject: str
) -> PlacedStructure:
    placed = PlacedStructure()
    if structure is None:
        return placed
    for side, found in ((placed.leading, structure.leading), (placed.trailing, structure.trailing)):
        for chapter, items in found.items():
            refs = [_place(placed, chapter, item, subject) for item in _kept(items, visible)]
            if refs:
                side[chapter] = refs
    return placed


def _kept(items: Sequence[StructureItem], visible: Mapping[uuid.UUID, ClaimView]) -> list[StructureItem]:
    kept: list[StructureItem] = []
    pending: list[StructureItem] = []
    for item in items:
        if isinstance(item, StructureBlock):
            kept.append(item)
            pending = []
        elif not item.claim_ids:
            heads = [held for held in pending if isinstance(held, StructureText) and held.tag == HEADING_TAG]
            pending = [item] if item.tag == HEADING_TAG else [*heads, item]
        elif all(claim in visible for claim in item.claim_ids):
            kept += [*pending, item]
            pending = []
    return kept


def _place(placed: PlacedStructure, chapter: str, item: StructureItem, subject: str) -> str:
    if isinstance(item, StructureBlock):
        placed.blocks[item.label] = item
        placed.components[item.label] = ComponentEntry(
            label=item.label,
            chapter=chapter,
            anchor="#" + item.label.replace("/", "--"),
            kind=ANSWER_BLOCK_KIND,
            title=item.title,
            description=item.description,
            field=CHAPTER_FIELDS.get(chapter, DEFAULT_FIELD),
            fields=[],
            subjects=[CRAFT_SUBJECT.format(slug=subject)],
        )
        return item.label
    if item.claim_ids:
        discipline = item.field or CHAPTER_FIELDS.get(chapter, DEFAULT_FIELD)
        placed.drafts[item.unit_id] = DraftUnit(
            item.unit_id, chapter, discipline, item.text, item.claim_ids, tag=item.tag
        )
    else:
        placed.units[item.unit_id] = TextUnit(
            chapter=chapter, tag=item.tag, field=None, nodes=[item.text], claim_ids=[]
        )
    return item.unit_id
