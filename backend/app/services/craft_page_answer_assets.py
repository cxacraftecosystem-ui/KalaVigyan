from __future__ import annotations

import uuid
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from types import MappingProxyType

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import KnowledgePiece as PieceRow, Source
from app.research.chapter_keys import CHAPTER_KEYS, DISCIPLINE_CHAPTERS
from app.research.citations import SourceRef
from app.research.craft_chapters import PAGE_BLOCK_KINDS, AskedQuestion, ItemOrigin
from app.research.explainer import Block
from app.research.piece_reuse import curated_piece

from .chapter_draft import ChapterDraft, Drafted
from .knowledge_view import source_ref
from .piece_lookup import curated_claim_ids, stored_piece

__all__ = [
    "KIND_CHAPTERS",
    "REBUILT_KINDS",
    "AnswerPiece",
    "AnswerPieces",
    "answer_pieces",
    "joining_pieces",
    "with_answer_pieces",
]

ENGLISH = "en"
READERS = "READERS"
MODEL = "MODEL"
SIMULATION = "simulation"
KIND_CHAPTERS: Mapping[str, str] = MappingProxyType(
    {
        "process_ladder": "made",
        "reaction_player": "chem",
        "molecule_3d": "chem",
        "material_card": "chem",
        "simulation": "chem",
        "region_story": "why",
        "climate_risk": "why",
        "seasons": "why",
        "timeline_map": "history",
        "market_gi": "market",
        "what_if": "whatif",
        "artisan_voice": "people",
    }
)
REBUILT_KINDS = frozenset(
    {
        "process_ladder",
        "reaction_player",
        "molecule_3d",
        "material_card",
        "region_story",
        "climate_risk",
        "seasons",
        "timeline_map",
        "market_gi",
        "key_facts",
    }
)


@dataclass(frozen=True)
class AnswerPiece:
    piece_id: uuid.UUID
    block: Block
    facet: str
    topic_key: str
    claim_ids: tuple[uuid.UUID, ...]
    created_at: datetime

    @property
    def chapter(self) -> str | None:
        return KIND_CHAPTERS.get(self.block.kind) or DISCIPLINE_CHAPTERS.get(self.facet)

    def origin(self) -> ItemOrigin:
        asked = AskedQuestion(text=None, asked_in=self.created_at.strftime("%Y-%m"))
        model = getattr(self.block, "model", None) if self.block.kind == SIMULATION else None
        made = getattr(self.block, "created_at", None)
        return ItemOrigin(
            basis=READERS,
            generated=MODEL if model and made else None,
            model=model if model and made else None,
            generated_on=made.strftime("%Y-%m-%d") if model and made else None,
            from_question=asked,
        )


@dataclass(frozen=True)
class AnswerPieces:
    pieces: tuple[AnswerPiece, ...] = ()
    sources: Mapping[str, SourceRef] = field(default_factory=dict)


async def answer_pieces(session: AsyncSession, craft_id: uuid.UUID) -> AnswerPieces:
    rows = await _readers_rows(session, craft_id)
    found = []
    for row in rows:
        piece = stored_piece(row)
        if piece is not None:
            found.append(
                AnswerPiece(
                    piece.id,
                    piece.payload,
                    piece.facet,
                    piece.topic_key,
                    tuple(piece.claim_ids),
                    piece.created_at,
                )
            )
    wanted = sorted({sid for piece in found for sid in piece.block.cited_source_ids() if _is_uuid(sid)})
    sources = await session.scalars(select(Source).where(Source.id.in_(wanted))) if wanted else []
    refs = {str(row.id): SourceRef.model_validate(source_ref(row)) for row in sources}
    return AnswerPieces(tuple(found), refs)


async def _readers_rows(session: AsyncSession, craft_id: uuid.UUID) -> list[PieceRow]:
    rows = await session.scalars(
        select(PieceRow)
        .where(
            PieceRow.craftId == craft_id,
            PieceRow.label.is_(None),
            PieceRow.language == ENGLISH,
            PieceRow.readingStyle.is_(None),
            PieceRow.staleSince.is_(None),
            PieceRow.supersededById.is_(None),
            PieceRow.hiddenAt.is_(None),
            PieceRow.kind.in_(sorted(PAGE_BLOCK_KINDS)),
        )
        .order_by(PieceRow.createdAt.desc(), PieceRow.id)
    )
    listed = list(rows)
    answerless = (claim for row in listed if row.createdFromAnswerId is None for claim in row.claimIds)
    curated = await curated_claim_ids(session, answerless)
    return [row for row in listed if not curated_piece(row.createdFromAnswerId, row.claimIds, curated)]


def joining_pieces(
    pieces: Sequence[AnswerPiece], drafts: Sequence[ChapterDraft], listed: Collection[uuid.UUID]
) -> list[AnswerPiece]:
    shown = {claim_id for draft in drafts for drafted in draft.items for claim_id in _cited(drafted)}
    kinds = {(draft.key, drafted.kind) for draft in drafts for drafted in draft.items}
    best: dict[tuple[str, str, str], AnswerPiece] = {}
    for piece in pieces:
        chapter = piece.chapter
        cited = set(piece.claim_ids)
        if chapter is None or not cited or not cited <= set(listed):
            continue
        present = (chapter, piece.block.kind) in kinds
        if present and (piece.block.kind in REBUILT_KINDS or cited <= shown):
            continue
        slot = (chapter, piece.block.kind, piece.topic_key)
        kept = best.get(slot)
        if kept is None or (len(cited), piece.created_at) > (len(set(kept.claim_ids)), kept.created_at):
            best[slot] = piece
    return list(best.values())


def with_answer_pieces(
    drafts: Sequence[ChapterDraft], pieces: Sequence[AnswerPiece], listed: Collection[uuid.UUID]
) -> list[ChapterDraft]:
    joined: dict[str, list[Drafted]] = {}
    for n, piece in enumerate(joining_pieces(pieces, drafts, listed), start=1):
        chapter = str(piece.chapter)
        block = piece.block.model_copy(update={"id": f"{chapter}.reader-{n}"})
        joined.setdefault(chapter, []).append(
            Drafted.of_block(block, origin=piece.origin(), piece_id=piece.piece_id)
        )
    placed = [ChapterDraft(d.key, d.opener, [*d.items, *joined.pop(d.key, [])]) for d in drafts]
    placed += [ChapterDraft(key, None, items) for key, items in joined.items()]
    return sorted(placed, key=lambda draft: CHAPTER_KEYS.index(draft.key))


def _cited(drafted: Drafted) -> set[uuid.UUID]:
    if drafted.block is not None:
        return {uuid.UUID(str(claim_id)) for claim_id in drafted.block.cited_claim_ids()}
    part = drafted.part
    found = (c.claim_id for s in part.cited_sentences() for c in s.citations) if part is not None else ()
    return {uuid.UUID(claim_id) for claim_id in found}


def _is_uuid(value: str) -> bool:
    try:
        uuid.UUID(value)
    except ValueError:
        return False
    return True
