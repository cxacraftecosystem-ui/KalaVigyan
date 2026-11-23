from __future__ import annotations

import logging
from collections.abc import Collection, Sequence

from sqlalchemy import ColumnElement, and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Craft, KnowledgePiece as PieceRow
from app.research.blocks_place import RegionStoryBlock
from app.research.knowledge_pieces import KnowledgePiece, region_topic
from app.research.piece_reuse import REGION_STORY_FACETS, REGION_STORY_KIND
from app.research.vocabulary import CANONICAL_LANGUAGE

from .piece_lookup import PIECE_CANDIDATES_MAX, stored_piece
from .place_offers import REGION_RIVERS_MAX, mapped_districts
from .river_store import rivers_crossing, stored_trace_problems

__all__ = ["basin_keys", "district_story_pieces", "region_story_pieces"]

logger = logging.getLogger(__name__)

PROBLEMS_SHOWN = 5


async def region_story_pieces(
    session: AsyncSession, craft: Craft, facets: Collection[str]
) -> list[KnowledgePiece]:
    lgds = await mapped_districts(session, craft) if facets else ()
    if not lgds:
        return []
    crossings = await rivers_crossing(session, lgds, limit=REGION_RIVERS_MAX)
    keys = basin_keys(facets, [crossing.main_riv for crossing in crossings])
    told = and_(PieceRow.districtLgds.contains(list(lgds)), PieceRow.districtLgds.contained_by(list(lgds)))
    return await _stored_stories(session, facets, or_(PieceRow.topicKey.in_(keys), told))


async def district_story_pieces(session: AsyncSession, district_lgd: int) -> list[KnowledgePiece]:
    crossings = await rivers_crossing(session, [district_lgd], limit=REGION_RIVERS_MAX)
    keys = basin_keys(REGION_STORY_FACETS, [crossing.main_riv for crossing in crossings])
    told = PieceRow.districtLgds.contains([district_lgd])
    return await _stored_stories(session, REGION_STORY_FACETS, or_(PieceRow.topicKey.in_(keys), told))


def basin_keys(facets: Collection[str], basins: Sequence[int]) -> list[str]:
    keys = [
        region_topic(facet, main_riv=main_riv, district_lgds=()) for facet in facets for main_riv in basins
    ]
    return list(dict.fromkeys(keys))


async def _stored_stories(
    session: AsyncSession, facets: Collection[str], placed: ColumnElement[bool]
) -> list[KnowledgePiece]:
    rows = await session.scalars(
        select(PieceRow)
        .where(
            PieceRow.craftId.is_(None),
            PieceRow.kind == REGION_STORY_KIND,
            PieceRow.facet.in_(list(facets)),
            placed,
            PieceRow.language == CANONICAL_LANGUAGE,
            PieceRow.supersededById.is_(None),
            PieceRow.staleSince.is_(None),
        )
        .order_by(PieceRow.createdAt.desc(), PieceRow.id)
        .limit(PIECE_CANDIDATES_MAX)
    )
    pieces = [piece for row in rows.all() if (piece := stored_piece(row)) is not None]
    return [piece for piece in pieces if await _river_still_stored(session, piece)]


async def _river_still_stored(session: AsyncSession, piece: KnowledgePiece) -> bool:
    story = piece.payload
    if not isinstance(story, RegionStoryBlock) or story.river is None:
        return True
    problems = await stored_trace_problems(session, story.river)
    if problems:
        logger.info(
            "stored region story %s no longer follows the stored river: %s",
            piece.id,
            "; ".join(problems[:PROBLEMS_SHOWN]),
        )
    return not problems
