from __future__ import annotations

import logging
import uuid
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    AdminDistrict,
    Craft,
    CraftLocation,
    CuratedCategoryClaim,
    CuratedClaim,
    KnowledgePiece as PieceRow,
)
from app.research.crafts import CraftRef
from app.research.knowledge_pieces import PIECE_SCHEMA_VERSION, KnowledgePiece
from app.research.piece_reuse import ClaimState
from app.research.piece_topics import TopicSubjects
from app.research.reading_style import ReadingStyle
from app.research.retrieval import OPEN_CHUNK_ACLS
from app.research.term_marking import TermMarker
from app.research.vocabulary import CANONICAL_LANGUAGE

from . import knowledge_view
from .answer_events import CitedClaims, cited_claims
from .term_glossary import glossary_entries

__all__ = [
    "PIECE_CANDIDATES_MAX",
    "PieceAsk",
    "PieceLookup",
    "ReusedSection",
    "answerless_claims",
    "candidate_pieces",
    "claim_states",
    "craft_districts",
    "curated_claim_ids",
    "stored_piece",
    "stored_pieces",
    "topic_subjects",
    "view_states",
]

logger = logging.getLogger(__name__)

PIECE_CANDIDATES_MAX = 200


@dataclass(frozen=True)
class PieceAsk:
    question: str
    craft: CraftRef | None
    facets: tuple[str, ...]
    depth: str
    fresh: bool = False
    reading_style: ReadingStyle | None = None


@dataclass(frozen=True)
class ReusedSection:
    pieces: tuple[KnowledgePiece, ...]
    cited: CitedClaims
    curated: frozenset[uuid.UUID] = frozenset()


@dataclass(frozen=True)
class PieceLookup:
    craft_id: uuid.UUID | None = None
    topics: Mapping[str, str] = field(default_factory=dict)
    craft_slug: str | None = None
    reused: Mapping[str, ReusedSection] = field(default_factory=dict)


async def topic_subjects(session: AsyncSession, craft: Craft, question: str) -> TopicSubjects:
    marker = TermMarker(await glossary_entries(session, [craft.id]))
    terms = tuple(span.term_key for span in marker.spans(question))
    return TopicSubjects(
        craft_slug=craft.slug, question_terms=terms, districts=await craft_districts(session, craft)
    )


async def craft_districts(session: AsyncSession, craft: Craft) -> tuple[str, ...]:
    names = await session.scalars(
        select(AdminDistrict.name)
        .join(CraftLocation, CraftLocation.districtLgd == AdminDistrict.lgd)
        .where(CraftLocation.craftId == craft.id)
        .distinct()
        .order_by(AdminDistrict.name)
    )
    return tuple(names)


async def candidate_pieces(
    session: AsyncSession, craft_id: uuid.UUID, topics: Mapping[str, str]
) -> list[KnowledgePiece]:
    rows = await session.scalars(
        select(PieceRow)
        .where(
            PieceRow.craftId == craft_id,
            PieceRow.facet.in_(list(topics)),
            PieceRow.topicKey.in_(list(topics.values())),
            PieceRow.language == CANONICAL_LANGUAGE,
        )
        .order_by(PieceRow.createdAt.desc(), PieceRow.id)
        .limit(PIECE_CANDIDATES_MAX)
    )
    pieces = [stored_piece(row) for row in rows]
    return [piece for piece in pieces if piece is not None]


async def curated_claim_ids(session: AsyncSession, claim_ids: Iterable[uuid.UUID]) -> frozenset[uuid.UUID]:
    wanted = list(dict.fromkeys(claim_ids))
    if not wanted:
        return frozenset()
    crafts = select(CuratedClaim.claimId).where(CuratedClaim.claimId.in_(wanted))
    categories = select(CuratedCategoryClaim.claimId).where(CuratedCategoryClaim.claimId.in_(wanted))
    return frozenset((await session.scalars(crafts.union(categories))).all())


def answerless_claims(pieces: Iterable[KnowledgePiece]) -> list[uuid.UUID]:
    return [claim for piece in pieces if piece.created_from_answer_id is None for claim in piece.claim_ids]


async def claim_states(
    session: AsyncSession, pieces: Sequence[KnowledgePiece], *, acls: Sequence[str] = OPEN_CHUNK_ACLS
) -> tuple[dict[uuid.UUID, ClaimState], CitedClaims]:
    wanted = dict.fromkeys(claim for piece in pieces for claim in piece.claim_ids)
    views, sources = await knowledge_view.claims_by_id(session, wanted, acls=acls)
    return view_states(views.values()), cited_claims(list(views.values()), sources)


def view_states(views: Iterable[knowledge_view.ClaimView]) -> dict[uuid.UUID, ClaimState]:
    return {
        view.id: ClaimState(level=view.level, citation_ids=frozenset(c["id"] for c in view.citations))
        for view in views
    }


def stored_piece(row: PieceRow) -> KnowledgePiece | None:
    try:
        return KnowledgePiece.model_validate(
            {
                "schemaVersion": PIECE_SCHEMA_VERSION,
                "id": row.id,
                "craftId": row.craftId,
                "kind": row.kind,
                "facet": row.facet,
                "topicKey": row.topicKey,
                "language": row.language,
                "depth": row.depth,
                "payload": row.payload,
                "claimIds": row.claimIds,
                "sourceIds": row.sourceIds,
                "contentHash": row.contentHash,
                "createdFromAnswerId": row.createdFromAnswerId,
                "createdAt": row.createdAt,
                "staleSince": row.staleSince,
                "supersededById": row.supersededById,
                "hiddenAt": row.hiddenAt,
                "readingStyle": row.readingStyle,
            }
        )
    except ValidationError as refused:
        logger.warning("stored piece %s no longer meets the piece contract: %s", row.id, refused)
        return None


async def stored_pieces(
    session: AsyncSession, piece_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, KnowledgePiece]:
    if not piece_ids:
        return {}
    rows = await session.scalars(select(PieceRow).where(PieceRow.id.in_(list(piece_ids))))
    pieces = (stored_piece(row) for row in rows)
    return {piece.id: piece for piece in pieces if piece is not None}
