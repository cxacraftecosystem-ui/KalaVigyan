from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.models.component_kinds import LINK_TOOL_KINDS

from .component_specs_blocks import ANSWER_BLOCK_KIND
from .kin_crafts import KIN_KIND
from .monograph_document import MonographDocument
from .monograph_page import ComponentEntry, MonographContent
from .quotes import quote_key
from .spec_strings import spec_strings

__all__ = ["OPENING", "PICTURE_KIND", "ReadPage", "Sentence", "cite_keys", "node_text"]

OPENING = "opening"
PICTURE_KIND = "picture_plate"
SENTENCE_TAG = "p"
CITE_MARK = "cite"
TOLD_TAGS = frozenset({"p", "li", "dd", "span"})
SENTENCE_END = re.compile(r"[.!?][\"'’”)\]]*$")
BLOCK_KEY = "block"


@dataclass(frozen=True)
class Sentence:
    unit_id: str
    text: str
    field: str | None
    chapter: str
    claim_ids: tuple[str, ...]


def node_text(nodes: Sequence[Any]) -> str:
    return "".join(
        node if isinstance(node, str) else node_text(node.get("c", []))
        for node in nodes
        if isinstance(node, str | dict)
    )


@dataclass(frozen=True)
class ReadPage:
    document: MonographDocument
    sentences: tuple[Sentence, ...]
    within: Mapping[str, str]
    figures: tuple[ComponentEntry, ...]
    pictures: tuple[ComponentEntry, ...]
    told: tuple[Sentence, ...] = ()

    @classmethod
    def of(cls, document: MonographDocument) -> ReadPage:
        content = document.content
        within = {entry.ref: entry.within for entry in content.layout if entry.within is not None}
        placed = [entry.ref for entry in content.layout if entry.kind == "unit" and entry.within is None]
        sentences = tuple(
            Sentence(ref, node_text(unit.nodes).strip(), unit.field, unit.chapter, tuple(unit.claim_ids))
            for ref in placed
            if (unit := content.units.get(ref)) is not None and unit.tag == SENTENCE_TAG and unit.claim_ids
        )
        figures = tuple(c for c in content.components if c.kind not in (PICTURE_KIND, *LINK_TOOL_KINDS))
        pictures = tuple(c for c in content.components if c.kind == PICTURE_KIND)
        told = (*sentences, *_drawn_sentences(content), *_block_sentences(document))
        return cls(document, sentences, within, figures, pictures, told)

    def text(self, unit_id: str) -> str:
        unit = self.document.content.units.get(unit_id)
        return "" if unit is None else node_text(unit.nodes).strip()

    def held(self, label: str) -> list[str]:
        return [unit for unit, owner in self.within.items() if owner == label]

    def named(self, label: str) -> list[str]:
        units = self.document.content.units
        spec = self.document.specs.get(label, {})
        return list(dict.fromkeys([*self.held(label), *(ref for ref in spec_strings(spec) if ref in units)]))

    def cited(self, label: str) -> bool:
        content = self.document.content
        spec = self.document.specs.get(label, {})
        named = self.named(label)
        marks = [
            *cite_keys(spec),
            *(key for ref in named if ref in content.units for key in cite_keys(content.units[ref].nodes)),
        ]
        return (
            any(ref in content.citations for ref in named)
            or any(key in content.citations for key in marks)
            or bool(spec.get("sources"))
            or label in self.document.fragments
        )

    def plate(self, label: str) -> tuple[str, str, str]:
        spec = self.document.specs.get(label, {})
        figure = spec.get("figure") or {}
        captions = [
            self.text(str(c.get("unit"))) for c in figure.get("captions") or [] if isinstance(c, dict)
        ]
        credit = self.text(str(figure.get("credit"))) if figure.get("credit") else ""
        return str((spec.get("picture") or {}).get("src") or ""), " ".join(captions), credit

    def lede(self) -> list[Sentence]:
        return [sentence for sentence in self.sentences if sentence.chapter == OPENING]

    def by_field(self) -> Counter[str]:
        return Counter(sentence.field for sentence in self.sentences if sentence.field)

    def told_by_field(self) -> Counter[str]:
        told = dict.fromkeys((s.field, quote_key(s.text).casefold()) for s in self.told if s.field and s.text)
        return Counter(field for field, _ in told)


def _drawn_sentences(content: MonographContent) -> Iterator[Sentence]:
    kin = {component.label for component in content.components if component.kind == KIN_KIND}
    for entry in content.layout:
        unit = content.units.get(entry.ref) if entry.kind == "unit" and entry.within not in kin else None
        if unit is None or not unit.claim_ids or unit.tag not in TOLD_TAGS:
            continue
        text = node_text(unit.nodes).strip()
        if SENTENCE_END.search(text):
            yield Sentence(entry.ref, text, unit.field, unit.chapter, tuple(unit.claim_ids))


def _block_sentences(document: MonographDocument) -> Iterator[Sentence]:
    for component in document.content.components:
        if component.kind != ANSWER_BLOCK_KIND:
            continue
        block = document.specs.get(component.label, {}).get(BLOCK_KEY)
        for text, claims in _cited_texts(block):
            yield Sentence(component.label, text, component.field, component.chapter, claims)


def _cited_texts(value: Any) -> Iterator[tuple[str, tuple[str, ...]]]:
    if isinstance(value, list):
        for item in value:
            yield from _cited_texts(item)
        return
    if not isinstance(value, Mapping):
        return
    citations = value.get("citations")
    if isinstance(value.get("text"), str) and isinstance(citations, list) and citations:
        claims = tuple(str(c["claimId"]) for c in citations if isinstance(c, Mapping) and c.get("claimId"))
        yield value["text"].strip(), claims
    for item in value.values():
        yield from _cited_texts(item)


def cite_keys(value: Any) -> list[str]:
    if isinstance(value, Mapping):
        own = [str(value["key"])] if value.get("m") == CITE_MARK and "key" in value else []
        return [*own, *(key for item in value.values() for key in cite_keys(item))]
    if isinstance(value, list):
        return [key for item in value for key in cite_keys(item)]
    return []
