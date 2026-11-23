from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.errors import AppError, InvalidInput
from app.core.shielded import ShieldedWork
from app.data.craft_master_loader import ID_NAMESPACE
from app.models import KnowledgePiece as PieceRow
from app.models.enums import EXPLAINER_DEPTHS
from app.research.blocks import ProcessLadderBlock
from app.research.blocks_insight import MarketGiBlock
from app.research.blocks_matter import ReactionPlayerBlock
from app.research.blocks_play import SimulationBlock, WhatIfBlock
from app.research.depth import depth_at_least
from app.research.embedding import TextEmbedder, checked_vectors
from app.research.explainer import Block
from app.research.knowledge_pieces import (
    CLAIM_KEYED_KINDS,
    UNSTORED_BLOCK_KINDS,
    KnowledgePiece,
    PieceSlot,
    ReuseAsk,
    concept_slot,
    knowledge_piece,
    piece_district_lgds,
    piece_slot,
)
from app.research.piece_reuse import (
    REGION_STORY_FACETS,
    SIMULATION_FACETS,
    ClaimState,
    answered_first,
    curated_piece,
    reusable_groups,
    with_region_story,
    with_simulation,
)
from app.research.piece_topics import facet_topics
from app.research.reading_style import ReadingStyle
from app.research.retrieval import EVERY_CHUNK_ACLS
from app.retrieval.indexing import embed_pieces
from app.retrieval.text import query_text
from app.science.ladder import ladder_problems
from app.science.reaction_player import reaction_player_problems
from app.science.records import ProcessRecords
from app.science.what_if_check import what_if_problems

from . import knowledge_view
from .craft_process import process_records
from .piece_lookup import (
    PieceAsk,
    PieceLookup,
    ReusedSection,
    answerless_claims,
    candidate_pieces,
    claim_states,
    curated_claim_ids,
    topic_subjects,
)
from .region_pieces import region_story_pieces
from .simulation_pieces import simulation_pieces
from .stored_fields import curated_field_counts, fields_held

__all__ = [
    "BuiltSection",
    "PieceStore",
    "SqlPieceStore",
    "kept_for",
    "kept_pieces",
    "piece_id",
    "piece_values",
    "process_problems",
    "storable",
]

logger = logging.getLogger(__name__)

NO_DISTANCE = 2.0
PROCESS_BLOCKS = (ProcessLadderBlock, ReactionPlayerBlock, WhatIfBlock)


@dataclass(frozen=True)
class BuiltSection:
    facet: str
    blocks: tuple[Block, ...]
    deepened: bool = False


class PieceStore(Protocol):
    async def reusable(self, ask: PieceAsk) -> PieceLookup: ...

    async def keep(
        self,
        lookup: PieceLookup,
        *,
        answer_id: uuid.UUID,
        depth: str,
        sections: Sequence[BuiltSection],
        reading_style: ReadingStyle | None = None,
    ) -> None: ...

    async def fields(self, craft_slug: str) -> tuple[str, ...]: ...


def piece_id(answer_id: uuid.UUID, block_id: str) -> uuid.UUID:
    return uuid.uuid5(ID_NAMESPACE, f"knowledge-piece:{answer_id}:{block_id}")


def storable(block: Block) -> bool:
    if block.kind in UNSTORED_BLOCK_KINDS or block.reuse is not None:
        return False
    return bool(block.cited_claim_ids()) and bool(block.cited_source_ids())


class SqlPieceStore:
    def __init__(
        self, sessions: async_sessionmaker[AsyncSession], *, embed: TextEmbedder, shield: ShieldedWork
    ) -> None:
        self._sessions = sessions
        self._embed = embed
        self._shield = shield

    async def reusable(self, ask: PieceAsk) -> PieceLookup:
        if ask.craft is None:
            return PieceLookup()
        async with self._sessions() as session:
            craft = await knowledge_view.resolve_craft(session, ask.craft.slug)
            if craft is None:
                return PieceLookup()
            topics = facet_topics(ask.facets, await topic_subjects(session, craft, ask.question))
            if ask.fresh or not topics:
                return PieceLookup(craft_id=craft.id, topics=topics, craft_slug=craft.slug)
            pieces = await candidate_pieces(session, craft.id, topics)
            region_facets = [facet for facet in topics if facet in REGION_STORY_FACETS]
            regions = (
                await region_story_pieces(session, craft, region_facets) if pieces and region_facets else []
            )
            rested_on = {claim for piece in pieces for claim in piece.claim_ids}
            simulations = await simulation_pieces(session, rested_on, set(topics) & SIMULATION_FACETS)
            states, cited = await claim_states(session, [*pieces, *regions], acls=EVERY_CHUNK_ACLS)
            checked = any(isinstance(piece.payload, PROCESS_BLOCKS) for piece in pieces)
            records = await process_records(session, craft, acls=EVERY_CHUNK_ACLS) if checked else None
            curated = await curated_claim_ids(session, answerless_claims(pieces))
        reused: dict[str, ReusedSection] = {}
        for facet, topic in topics.items():
            reuse = ReuseAsk(
                craft_id=craft.id,
                facet=facet,
                topic_key=topic,
                depth=ask.depth,
                reading_style=ask.reading_style,
            )
            groups = answered_first(_facet_groups(pieces, reuse, states, records), curated)
            if groups:
                closest = await self._closest(groups, ask.question)
                shown = with_region_story(closest, regions, depth=ask.depth, current=states)
                shown = with_simulation(shown, simulations, depth=ask.depth, current=states)
                reused[facet] = ReusedSection(pieces=shown, cited=cited, curated=curated)
        return PieceLookup(craft_id=craft.id, topics=topics, reused=reused, craft_slug=craft.slug)

    async def keep(
        self,
        lookup: PieceLookup,
        *,
        answer_id: uuid.UUID,
        depth: str,
        sections: Sequence[BuiltSection],
        reading_style: ReadingStyle | None = None,
    ) -> None:
        pieces = kept_pieces(
            lookup, answer_id=answer_id, depth=depth, sections=sections, reading_style=reading_style
        )
        if pieces:
            await self._shield.run(self._kept(pieces), name="knowledge pieces")

    async def fields(self, craft_slug: str) -> tuple[str, ...]:
        async with self._sessions() as session:
            craft = await knowledge_view.resolve_craft(session, craft_slug)
            return fields_held(await curated_field_counts(session, craft)) if craft is not None else ()

    async def _closest(
        self, groups: Sequence[tuple[KnowledgePiece, ...]], question: str
    ) -> tuple[KnowledgePiece, ...]:
        if len(groups) == 1:
            return groups[0]
        vector = checked_vectors(await self._embed([query_text(question)]), expected=1)[0]
        ids = [piece.id for group in groups for piece in group]
        async with self._sessions() as session:
            rows = await session.execute(
                select(PieceRow.id, PieceRow.embedding.cosine_distance(vector)).where(PieceRow.id.in_(ids))
            )
            distances = {row[0]: row[1] for row in rows if row[1] is not None}
        return min(groups, key=lambda group: min(distances.get(piece.id, NO_DISTANCE) for piece in group))

    async def _kept(self, pieces: Sequence[KnowledgePiece]) -> None:
        async with self._sessions() as session:
            for piece in pieces:
                await _insert(session, piece)
                await _supersede(session, piece)
            await session.commit()
            try:
                await embed_pieces(session, self._embed, piece_ids=[piece.id for piece in pieces])
            except AppError:
                logger.warning(
                    "knowledge pieces kept without vectors; embed_knowledge fills them", exc_info=True
                )


def _facet_groups(
    pieces: Sequence[KnowledgePiece],
    reuse: ReuseAsk,
    states: Mapping[uuid.UUID, ClaimState],
    records: ProcessRecords | None,
) -> list[tuple[KnowledgePiece, ...]]:
    return [group for group in reusable_groups(pieces, reuse, states) if _process_blocks_hold(group, records)]


def _process_blocks_hold(group: Sequence[KnowledgePiece], records: ProcessRecords | None) -> bool:
    checked = [piece.payload for piece in group if isinstance(piece.payload, PROCESS_BLOCKS)]
    if checked and records is None:
        return False
    problems = [problem for block in checked for problem in process_problems(block, records)]
    if problems:
        logger.info("a stored block no longer matches the process rows: %s", "; ".join(problems))
    return not problems


def process_problems(block: Block, records: ProcessRecords) -> list[str]:
    if isinstance(block, ReactionPlayerBlock):
        return reaction_player_problems(block, records)
    if isinstance(block, ProcessLadderBlock):
        return ladder_problems(block, records)
    if isinstance(block, WhatIfBlock):
        return what_if_problems(block, records)
    return []


def kept_pieces(
    lookup: PieceLookup,
    *,
    answer_id: uuid.UUID,
    depth: str,
    sections: Sequence[BuiltSection],
    reading_style: ReadingStyle | None = None,
) -> list[KnowledgePiece]:
    created_at = datetime.now(UTC)
    kept: list[KnowledgePiece] = []
    for section in sections:
        shared = _section_slot(lookup, section, depth)
        for block in section.blocks:
            slot = _block_slot(block, shared, section.facet, depth) if kept_for(block, lookup) else None
            if slot is not None:
                piece = piece_id(answer_id, block.id)
                kept.append(
                    knowledge_piece(
                        block,
                        slot,
                        piece_id=piece,
                        answer_id=answer_id,
                        created_at=created_at,
                        reading_style=reading_style,
                    )
                )
    return kept


def _section_slot(lookup: PieceLookup, section: BuiltSection, depth: str) -> PieceSlot | None:
    if section.deepened or lookup.craft_id is None or section.facet not in lookup.topics:
        return None
    return PieceSlot(lookup.craft_id, section.facet, lookup.topics[section.facet], depth)


def _block_slot(block: Block, shared: PieceSlot | None, facet: str, depth: str) -> PieceSlot | None:
    try:
        if isinstance(block, SimulationBlock):
            return concept_slot(block, facet, depth)
        return piece_slot(block, shared) if shared is not None else None
    except InvalidInput:
        logger.info("block %s names no topic key short enough to be stored", block.id)
        return None


def kept_for(block: Block, lookup: PieceLookup) -> bool:
    if isinstance(block, MarketGiBlock) and block.craft.slug != lookup.craft_slug:
        return False
    return storable(block)


def piece_values(piece: KnowledgePiece) -> dict[str, Any]:
    return {
        "id": piece.id,
        "craftId": piece.craft_id,
        "kind": piece.kind,
        "facet": piece.facet,
        "topicKey": piece.topic_key,
        "language": piece.language,
        "depth": piece.depth,
        "payload": piece.payload.model_dump(mode="json", by_alias=True),
        "claimIds": piece.claim_ids,
        "sourceIds": piece.source_ids,
        "contentHash": piece.content_hash,
        "createdFromAnswerId": piece.created_from_answer_id,
        "createdAt": piece.created_at,
        "readingStyle": piece.reading_style,
        "districtLgds": piece_district_lgds(piece),
    }


async def _insert(session: AsyncSession, piece: KnowledgePiece) -> None:
    await session.execute(insert(PieceRow).values(piece_values(piece)).on_conflict_do_nothing())


async def _supersede(session: AsyncSession, piece: KnowledgePiece) -> None:
    shallower = [depth for depth in EXPLAINER_DEPTHS if depth_at_least(piece.depth, depth)]
    same_claims = [PieceRow.claimIds == piece.claim_ids] if piece.kind in CLAIM_KEYED_KINDS else []
    rows = await session.execute(
        select(PieceRow.id, PieceRow.createdFromAnswerId, PieceRow.claimIds).where(
            PieceRow.craftId == piece.craft_id,
            PieceRow.facet == piece.facet,
            PieceRow.topicKey == piece.topic_key,
            PieceRow.kind == piece.kind,
            PieceRow.depth.in_(shallower),
            PieceRow.readingStyle.is_not_distinct_from(piece.reading_style),
            PieceRow.id != piece.id,
            PieceRow.createdFromAnswerId.is_distinct_from(piece.created_from_answer_id),
            PieceRow.supersededById.is_(None),
            PieceRow.createdAt <= piece.created_at,
            *same_claims,
        )
    )
    found = rows.all()
    answerless = (claim for row in found if row.createdFromAnswerId is None for claim in row.claimIds)
    curated = await curated_claim_ids(session, answerless)
    older = [row.id for row in found if not curated_piece(row.createdFromAnswerId, row.claimIds, curated)]
    if older:
        await session.execute(update(PieceRow).where(PieceRow.id.in_(older)).values(supersededById=piece.id))
