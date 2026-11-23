from __future__ import annotations

import uuid
from collections.abc import Iterator, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass

from app.core.errors import InvalidInput
from app.curation.dossier import Dossier
from app.curation.overview import OverviewSentence
from app.data.district_register import load_district_codes
from app.research.blocks import ProseBlock
from app.research.knowledge_pieces import KnowledgePiece, PieceSlot, knowledge_piece, piece_content_hash
from app.research.piece_topics import FACET_NAMESPACES, PLACE_FACETS, TopicSubjects, facet_topic
from app.research.subject_keys import topic_key
from app.research.term_marking import GlossaryEntry, TermMarker

from .answer_events import CitedClaims
from .curated_index import CuratedPage, IndexFact, IndexOverview, IndexSection
from .curation_keys import CURATED_DEPTH, curated_id
from .curation_records import glossary_key, term_names
from .section_blocks import KeptSentence, prose_block, prose_problems

__all__ = [
    "LEDE_FACET",
    "LEDE_PART",
    "OverviewPieces",
    "curated_glossary",
    "indexed_overview",
    "overview_pieces",
    "piece_id_topic",
    "piece_topic",
    "placed_overview",
]

LEDE_PART = "lede"
LEDE_FACET = "OVERVIEW"


@dataclass(frozen=True)
class OverviewPieces:
    pieces: tuple[KnowledgePiece, ...]
    parts: Mapping[str, uuid.UUID]
    dropped: tuple[str, ...]
    sentences: Mapping[str, OverviewSentence]


def curated_glossary(dossier: Dossier) -> list[GlossaryEntry]:
    entries = {}
    for term in dossier.glossary:
        key = glossary_key(term)
        if key is not None:
            entries.setdefault(key, GlossaryEntry(key=key, surfaces=tuple(term_names(term))))
    return list(entries.values())


def piece_topic(facet: str, slug: str, districts: Sequence[int]) -> str:
    found = facet_topic(facet, TopicSubjects(craft_slug=slug, districts=tuple(districts)))
    return found or topic_key(FACET_NAMESPACES[facet], slug)


def piece_id_topic(facet: str, slug: str, districts: Sequence[int]) -> str:
    named = {lgd: name for (_, name), lgd in load_district_codes().districts.items()}
    names = [named[lgd] for lgd in districts if lgd in named]
    if facet in PLACE_FACETS and names:
        with suppress(InvalidInput):
            return topic_key(FACET_NAMESPACES[facet], *names)
    return topic_key(FACET_NAMESPACES[facet], slug)


def overview_pieces(
    dossier: Dossier, cited: CitedClaims, *, craft_id: uuid.UUID | None, districts: Sequence[int]
) -> OverviewPieces:
    marker = TermMarker(curated_glossary(dossier))
    pieces: list[KnowledgePiece] = []
    parts: dict[str, uuid.UUID] = {}
    dropped: list[str] = []
    placed: dict[str, OverviewSentence] = {}
    for part, facet, sentences in _parts(dossier):
        kept: list[tuple[KeptSentence, OverviewSentence]] = []
        for index, sentence in enumerate(sentences):
            candidate = _candidate(dossier.slug, sentence)
            problems = prose_problems([candidate], cited)
            if problems:
                dropped.append(f"overview.{part}.{index}: {'; '.join(problems)}")
            else:
                kept.append((candidate, sentence))
        if kept:
            block = prose_block(f"curation.{part.lower()}", [candidate for candidate, _ in kept], cited)
            block = _marked(block, marker)
            topics = (
                piece_topic(facet, dossier.slug, districts),
                piece_id_topic(facet, dossier.slug, districts),
            )
            piece = _piece(dossier, (craft_id, part, facet), block, topics)
            pieces.append(piece)
            parts[part] = piece.id
            placed.update(
                zip((s.id for s in piece.payload.cited_sentences()), (s for _, s in kept), strict=True)
            )
    return OverviewPieces(pieces=tuple(pieces), parts=parts, dropped=tuple(dropped), sentences=placed)


def _parts(dossier: Dossier) -> Iterator[tuple[str, str, Sequence[OverviewSentence]]]:
    yield LEDE_PART, LEDE_FACET, dossier.overview.lede
    for section in dossier.overview.sections:
        yield section.discipline, section.discipline, section.sentences


def _candidate(slug: str, sentence: OverviewSentence) -> KeptSentence:
    claims = tuple(curated_id(slug, claim_id) for claim_id in sentence.claim_ids)
    return KeptSentence(text=sentence.text, claim_ids=claims, evidence_ids=(), open_question=False)


def _marked(block: ProseBlock, marker: TermMarker) -> ProseBlock:
    payload = block.model_dump(mode="json", by_alias=True)
    for sentence in payload["sentences"]:
        sentence["terms"] = [
            span.model_dump(mode="json", by_alias=True) for span in marker.spans(sentence["text"])
        ]
    return ProseBlock.model_validate(payload)


def _piece(
    dossier: Dossier, part: tuple[uuid.UUID | None, str, str], block: ProseBlock, topics: tuple[str, str]
) -> KnowledgePiece:
    craft_id, name, facet = part
    topic, id_topic = topics
    piece_id = curated_id(dossier.slug, "piece", name, id_topic, piece_content_hash(block))
    slot = PieceSlot(craft_id, facet, topic, CURATED_DEPTH)
    return knowledge_piece(block, slot, piece_id=piece_id, answer_id=None, created_at=dossier.curated_at)


def placed_overview(key_facts: Sequence[IndexFact], overview: OverviewPieces) -> IndexOverview:
    sections = [
        IndexSection(discipline=part, piece_id=piece_id)
        for part, piece_id in overview.parts.items()
        if part != LEDE_PART
    ]
    return IndexOverview(
        lede_piece_id=overview.parts.get(LEDE_PART), sections=sections, key_facts=list(key_facts)
    )


def indexed_overview(index: CuratedPage, overview: OverviewPieces) -> CuratedPage:
    return index.model_copy(update={"overview": placed_overview(index.overview.key_facts, overview)})
