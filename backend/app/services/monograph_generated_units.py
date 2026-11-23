from __future__ import annotations

import hashlib
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from app.research.chapter_keys import CHAPTER_TITLES
from app.research.coverage_chapters import field_chapter
from app.research.monograph_page import CitedSource, Quote, TextUnit
from app.research.sections import DISCIPLINE_TITLES

from .craft_chapters import chapter_title
from .knowledge_view import ClaimView

__all__ = [
    "LEDE_FIELD",
    "LEDE_SENTENCES",
    "MASTHEAD_CHAPTER",
    "SOURCES_CHAPTER",
    "DraftUnit",
    "SourceBook",
    "SubjectRecord",
    "chapter_heading",
    "cited_nodes",
    "cited_unit",
    "heading_unit",
    "masthead_units",
    "section_units",
    "stored_source",
]

HEADING_PREFIX = "h-"
DIGEST_CHARS = 10
SOURCE_KEY_PREFIX = "g"
SENTENCE_TAG = "p"
HEADING_TAG = "h3"
CHAPTER_HEAD_TAG = "h2"
CHAPTER_HEAD_PREFIX = "chapter-"
MASTHEAD_CHAPTER = "opening"
SOURCES_CHAPTER = "sources"
LEDE_FIELD = "OVERVIEW"
LEDE_SENTENCES = 3
PLACE_SEPARATOR = ","
MASTHEAD_KICKER = "masthead-kicker"
MASTHEAD_TITLE = "masthead-title"
LABEL_PLACE = "label-place"
LABEL_GI = "label-gi"
MONOGRAPH_KICKER = "Monograph"
PLACE_TERM = "Place"
GI_TERM = "GI"
GI_REGISTERED = "Registered geographical indication"
OVERVIEW, GEOGRAPHY, POLICY = "OVERVIEW", "GEOGRAPHY", "POLICY"


@dataclass(frozen=True)
class SubjectRecord:
    name: str
    kicker: str | None = None
    place: str | None = None
    gi: bool = False


@dataclass(frozen=True)
class DraftUnit:
    unit_id: str
    chapter: str
    field: str
    text: str
    claim_ids: tuple[uuid.UUID, ...]
    tag: str = SENTENCE_TAG


class SourceBook:
    def __init__(self) -> None:
        self._keys: dict[str, str] = {}
        self.sources: dict[str, CitedSource] = {}

    def key(self, source: CitedSource) -> str:
        identity = source.url or source.title.casefold()
        found = self._keys.get(identity)
        if found is not None:
            return found
        number = len(self.sources) + 1
        key = f"{SOURCE_KEY_PREFIX}{number}"
        self._keys[identity] = key
        self.sources[key] = source.model_copy(update={"number": number})
        return key

    def known(self, source: CitedSource) -> str | None:
        return self._keys.get(source.url or source.title.casefold())


def stored_source(ref: Mapping[str, Any]) -> CitedSource:
    return CitedSource(
        number=1,
        title=ref["title"],
        full_title=None,
        publisher=ref.get("publisher"),
        year=ref.get("year"),
        grade=ref.get("reliability"),
        url=ref.get("url"),
        extra=None,
        dossier_source_id=None,
        kind=ref.get("kind"),
    )


def section_units(
    field: str,
    sentences: Sequence[Mapping[str, Any]],
    visible: Mapping[uuid.UUID, ClaimView],
    taken: set[str],
) -> list[DraftUnit]:
    chapter = field_chapter(field)
    units = []
    for sentence in sentences:
        claim_ids = tuple(dict.fromkeys(uuid.UUID(str(claim)) for claim in sentence["claimIds"]))
        if not claim_ids or any(claim not in visible for claim in claim_ids):
            continue
        unit_id = _unit_id(field, claim_ids, taken)
        units.append(DraftUnit(unit_id, chapter, field, str(sentence["text"]).strip(), claim_ids))
    return units


def chapter_heading(chapter: str, record: SubjectRecord) -> tuple[str, TextUnit] | None:
    if chapter not in CHAPTER_TITLES:
        return None
    place = record.place.split(PLACE_SEPARATOR)[0].strip() if record.place else None
    title = chapter_title(chapter, place=place, gi=record.gi)
    unit = TextUnit(chapter=chapter, tag=CHAPTER_HEAD_TAG, field=None, nodes=[title], claim_ids=[])
    return f"{CHAPTER_HEAD_PREFIX}{chapter}", unit


def heading_unit(field: str) -> tuple[str, TextUnit]:
    return f"{HEADING_PREFIX}{field.lower()}", TextUnit(
        chapter=field_chapter(field),
        tag=HEADING_TAG,
        field=field,
        nodes=[DISCIPLINE_TITLES[field]],
        claim_ids=[],
    )


def cited_unit(
    draft: DraftUnit,
    visible: Mapping[uuid.UUID, ClaimView],
    book: SourceBook,
    sources: Mapping[str, CitedSource],
) -> tuple[TextUnit, list[Quote]]:
    quotes: list[Quote] = []
    keys: list[str] = []
    for claim_id in draft.claim_ids:
        for cite in visible[claim_id].citations:
            stored = sources.get(str(cite["sourceId"]))
            if stored is None:
                continue
            key = book.key(stored)
            keys.append(key)
            quote = Quote(source=key, locator=cite.get("locator"), quote=cite.get("quote"))
            if quote not in quotes:
                quotes.append(quote)
    unit = TextUnit(
        chapter=draft.chapter,
        tag=draft.tag,
        field=draft.field,
        nodes=cited_nodes(draft.text, draft.unit_id, list(dict.fromkeys(keys))),
        claim_ids=[str(claim_id) for claim_id in draft.claim_ids],
    )
    return unit, quotes


def cited_nodes(text: str, cite_key: str, source_keys: Sequence[str]) -> list[dict[str, Any]]:
    if not source_keys:
        return [{"m": "s", "c": [text]}]
    head, _, last = text.rpartition(" ")
    cite = {"m": "cite", "key": cite_key, "g": list(source_keys), "c": [last]}
    return [{"m": "s", "c": [f"{head} ", cite] if head else [cite]}]


def masthead_units(record: SubjectRecord) -> dict[str, TextUnit]:
    kicker = [{"m": "span", "c": [MONOGRAPH_KICKER]}]
    if record.kicker:
        kicker.append({"m": "span", "c": [record.kicker]})
    rows: list[tuple[str, str, str, list[Any]]] = [
        (MASTHEAD_KICKER, "p", OVERVIEW, kicker),
        (MASTHEAD_TITLE, "h1", OVERVIEW, [record.name]),
    ]
    if record.place:
        rows += [
            (f"{LABEL_PLACE}-term", "dt", GEOGRAPHY, [PLACE_TERM]),
            (LABEL_PLACE, "dd", GEOGRAPHY, [record.place]),
        ]
    if record.gi:
        rows += [(f"{LABEL_GI}-term", "dt", POLICY, [GI_TERM]), (LABEL_GI, "dd", POLICY, [GI_REGISTERED])]
    return {
        unit_id: TextUnit(chapter=MASTHEAD_CHAPTER, tag=tag, field=field, nodes=nodes, claim_ids=[])
        for unit_id, tag, field, nodes in rows
    }


def _unit_id(field: str, claim_ids: Iterable[uuid.UUID], taken: set[str]) -> str:
    digest = hashlib.sha256(" ".join(sorted(str(claim) for claim in claim_ids)).encode("utf-8")).hexdigest()
    stem = f"{field.lower()}-{digest[:DIGEST_CHARS]}"
    unit_id, n = stem, 1
    while unit_id in taken:
        n += 1
        unit_id = f"{stem}-{n}"
    taken.add(unit_id)
    return unit_id
