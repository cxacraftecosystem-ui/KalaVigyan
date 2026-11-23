from __future__ import annotations

import hashlib
import itertools
import json
import uuid
from collections.abc import Collection
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal, Self

from pydantic import AwareDatetime, Field, TypeAdapter, model_validator

from app.models.enums import BASIN_PLACE_PREFIX

from .base import ContractModel
from .blocks import BlockBase, ReuseMarker
from .blocks_place import RegionStoryBlock
from .blocks_play import SimulationBlock
from .depth import depth_at_least
from .explainer import BUILT_BLOCK_KINDS, Block, with_payload_sentences
from .piece_topics import FACET_NAMESPACES, district_topic
from .reading_style import STYLED_PIECE_KINDS, ReadingStyle
from .subject_keys import TopicKey, topic_key
from .vocabulary import CANONICAL_LANGUAGE, AnswerLanguage, BlockKind, Depth, Discipline

__all__ = [
    "BASIN_SUBJECT_PREFIX",
    "CLAIM_KEYED_KINDS",
    "PIECE_SCHEMA_VERSION",
    "PIECE_SENTENCE_PREFIX_CHARS",
    "PIECE_STALE_CHANGES",
    "PLACEMENT_FIELDS",
    "REUSE_REFUSALS",
    "SIMULATION_NAMESPACE",
    "UNSTORED_BLOCK_KINDS",
    "KnowledgePiece",
    "PieceSlot",
    "ReuseAsk",
    "concept_slot",
    "knowledge_piece",
    "piece_content_hash",
    "piece_district_lgds",
    "piece_slot",
    "piece_text",
    "placed_block",
    "region_topic",
    "rests_on",
    "reuse_refusal",
    "shows_alike",
]

PIECE_SCHEMA_VERSION = 1
PIECE_STALE_CHANGES = ("RETRACTED", "LEVEL_CHANGED", "HIDDEN", "TEXT_CHANGED")
PLACEMENT_FIELDS = frozenset({"id", "reuse"})
REUSE_REFUSALS = (
    "CRAFT",
    "FACET",
    "TOPIC",
    "DEPTH",
    "STYLE",
    "STALE",
    "SUPERSEDED",
    "HIDDEN",
    "CLAIM_NOT_VISIBLE",
)
PIECE_SENTENCE_PREFIX_CHARS = 12
UNSTORED_BLOCK_KINDS = frozenset(
    {"quiz", "compare", "concept_graph", "climate_risk", "artisan_voice", "component"}
)
BASIN_SUBJECT_PREFIX = BASIN_PLACE_PREFIX
SIMULATION_NAMESPACE = "concept"
CLAIM_KEYED_KINDS = frozenset({"simulation"})
BLOCKS = TypeAdapter(Block)

ReuseRefusal = Literal[*REUSE_REFUSALS]


class KnowledgePiece(ContractModel):
    schema_version: Literal[1]
    id: uuid.UUID
    craft_id: uuid.UUID | None
    kind: BlockKind
    facet: Discipline
    topic_key: TopicKey
    language: AnswerLanguage
    depth: Depth
    payload: Block
    claim_ids: list[uuid.UUID] = Field(min_length=1)
    source_ids: list[str] = Field(min_length=1)
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_from_answer_id: uuid.UUID | None
    created_at: AwareDatetime
    stale_since: AwareDatetime | None
    superseded_by_id: uuid.UUID | None
    hidden_at: AwareDatetime | None
    reading_style: ReadingStyle | None = None

    @model_validator(mode="after")
    def _payload_and_what_it_rests_on_agree(self) -> Self:
        if self.reading_style is not None and self.kind not in STYLED_PIECE_KINDS:
            raise ValueError(f"piece {self.id} is a {self.kind} block, which every reading style shares")
        if self.language != CANONICAL_LANGUAGE:
            raise ValueError(
                f"piece {self.id} is stored in {CANONICAL_LANGUAGE}; translations are cached apart"
            )
        if self.payload.kind != self.kind or self.payload.reuse is not None:
            raise ValueError(f"piece {self.id} stores a {self.kind} block as built, with no reuse mark")
        if self.kind not in BUILT_BLOCK_KINDS:
            raise ValueError(f"piece {self.id} stores a {self.kind} block, which is not built yet")
        if self.kind in UNSTORED_BLOCK_KINDS:
            raise ValueError(f"piece {self.id} stores a {self.kind} block, which is rebuilt each time")
        cited = sorted({uuid.UUID(claim) for claim in self.payload.cited_claim_ids()})
        if self.claim_ids != cited:
            raise ValueError(f"piece {self.id} lists the claims its block cites, once each, sorted")
        if self.source_ids != sorted(self.payload.cited_source_ids()):
            raise ValueError(f"piece {self.id} lists the sources its block cites, once each, sorted")
        if self.content_hash != piece_content_hash(self.payload):
            raise ValueError(f"piece {self.id} content hash does not match its block")
        if self.superseded_by_id == self.id:
            raise ValueError(f"piece {self.id} cannot supersede itself")
        return self


class ReuseAsk(ContractModel):
    craft_id: uuid.UUID | None
    facet: Discipline
    topic_key: TopicKey
    depth: Depth
    reading_style: ReadingStyle | None = None


def piece_content_hash(block: BlockBase) -> str:
    plain = block.model_dump(mode="json", by_alias=True, exclude=PLACEMENT_FIELDS)
    canonical = json.dumps(plain, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def shows_alike(block: BlockBase, other: BlockBase) -> bool:
    return _shown_content(block) == _shown_content(other)


def rests_on(piece: KnowledgePiece, claim_ids: Collection[uuid.UUID]) -> bool:
    return not set(claim_ids).isdisjoint(piece.claim_ids)


def reuse_refusal(
    piece: KnowledgePiece, ask: ReuseAsk, visible_claim_ids: Collection[uuid.UUID]
) -> ReuseRefusal | None:
    matches = (
        ("CRAFT", piece.craft_id == ask.craft_id),
        ("FACET", piece.facet == ask.facet),
        ("TOPIC", piece.topic_key == ask.topic_key),
        ("DEPTH", depth_at_least(piece.depth, ask.depth)),
        ("STYLE", piece.kind not in STYLED_PIECE_KINDS or piece.reading_style == ask.reading_style),
        ("STALE", piece.stale_since is None),
        ("SUPERSEDED", piece.superseded_by_id is None),
        ("HIDDEN", piece.hidden_at is None),
        ("CLAIM_NOT_VISIBLE", set(piece.claim_ids) <= set(visible_claim_ids)),
    )
    return next((refusal for refusal, holds in matches if not holds), None)


@dataclass(frozen=True)
class PieceSlot:
    craft_id: uuid.UUID | None
    facet: str
    topic_key: str
    depth: str


def knowledge_piece(
    block: BlockBase,
    slot: PieceSlot,
    *,
    piece_id: uuid.UUID,
    answer_id: uuid.UUID | None,
    created_at: datetime,
    reading_style: ReadingStyle | None = None,
) -> KnowledgePiece:
    payload = _piece_sentence_ids(block.model_dump(mode="json", by_alias=True) | {"reuse": None}, piece_id)
    stored = BLOCKS.validate_python(payload)
    return KnowledgePiece(
        schema_version=PIECE_SCHEMA_VERSION,
        id=piece_id,
        craft_id=slot.craft_id,
        kind=stored.kind,
        facet=slot.facet,
        topic_key=slot.topic_key,
        language=CANONICAL_LANGUAGE,
        depth=slot.depth,
        payload=stored,
        claim_ids=sorted({uuid.UUID(claim) for claim in stored.cited_claim_ids()}),
        source_ids=sorted(stored.cited_source_ids()),
        content_hash=piece_content_hash(stored),
        created_from_answer_id=answer_id,
        created_at=created_at,
        stale_since=None,
        superseded_by_id=None,
        hidden_at=None,
        reading_style=reading_style if stored.kind in STYLED_PIECE_KINDS else None,
    )


def placed_block(piece: KnowledgePiece, block_id: str) -> Block:
    marker = ReuseMarker(piece_id=piece.id, stored_at=piece.created_at)
    return piece.payload.model_copy(update={"id": block_id, "reuse": marker})


def piece_text(block: BlockBase) -> str:
    return " ".join([*(sentence.text for sentence in block.cited_sentences()), *block.shown_labels()])


def piece_slot(block: BlockBase, slot: PieceSlot) -> PieceSlot:
    if isinstance(block, SimulationBlock):
        return concept_slot(block, slot.facet, slot.depth)
    if not isinstance(block, RegionStoryBlock):
        return slot
    main_riv = block.river.main_riv if block.river is not None else None
    lgds = [district.district_lgd for district in block.districts]
    return PieceSlot(
        None, slot.facet, region_topic(slot.facet, main_riv=main_riv, district_lgds=lgds), slot.depth
    )


def concept_slot(block: SimulationBlock, facet: str, depth: str) -> PieceSlot:
    return PieceSlot(None, facet, topic_key(SIMULATION_NAMESPACE, block.concept), depth)


def region_topic(facet: str, *, main_riv: int | None, district_lgds: Collection[int]) -> str:
    if main_riv is not None:
        return topic_key(FACET_NAMESPACES[facet], f"{BASIN_SUBJECT_PREFIX}-{main_riv}")
    return district_topic(FACET_NAMESPACES[facet], district_lgds)


def piece_district_lgds(piece: KnowledgePiece) -> list[int]:
    story = piece.payload
    if not isinstance(story, RegionStoryBlock) or story.river is not None:
        return []
    return sorted({district.district_lgd for district in story.districts})


def _piece_sentence_ids(payload: dict[str, Any], piece_id: uuid.UUID) -> dict[str, Any]:
    prefix = f"p{piece_id.hex[:PIECE_SENTENCE_PREFIX_CHARS]}"
    counter = itertools.count(1)
    return with_payload_sentences(payload, lambda sentence: {**sentence, "id": f"{prefix}.{next(counter)}"})


def _shown_content(block: BlockBase) -> dict[str, Any]:
    plain = block.model_dump(mode="json", by_alias=True, exclude=PLACEMENT_FIELDS)
    return with_payload_sentences(plain, lambda sentence: {**sentence, "id": "", "terms": []})
