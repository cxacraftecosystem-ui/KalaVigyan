from __future__ import annotations

import itertools
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.geo.district_view import DistrictLocation, DistrictRecords
from app.geo.places import DISTRICT_PRECISIONS
from app.models import AdminDistrict, Craft, CraftLocation, KnowledgePiece as PieceRow, Source
from app.models.enums import EXPLAINER_DEPTHS
from app.research.blocks_place import DistrictRef
from app.research.citations import SourceRef
from app.research.crafts import CraftRef
from app.research.datasets import BOUNDARY_DATASET_CODE
from app.research.explainer import Block, with_payload_sentences
from app.research.knowledge_pieces import KnowledgePiece, ReuseAsk, placed_block, reuse_refusal
from app.research.piece_reuse import ClaimState, visible_as_cited
from app.research.piece_topics import district_subject
from app.research.retrieval import OPEN_CHUNK_ACLS, RESTRICTED_SENSITIVITY
from app.research.subject_keys import SUBJECT_JOINER
from app.research.vocabulary import CANONICAL_LANGUAGE

from .knowledge_view import craft_ref, source_ref
from .piece_lookup import PIECE_CANDIDATES_MAX, claim_states, stored_piece
from .place_offers import district_refs
from .region_pieces import district_story_pieces
from .region_records import dataset_records, district_values, located_places

__all__ = ["LAND_BLOCK_PREFIX", "LAND_FACET_ORDER", "district_records"]

LAND_BLOCK_PREFIX = "land.b"
LAND_FACET_ORDER = ("GEOGRAPHY", "GEOLOGY", "CLIMATE")
SHALLOWEST = EXPLAINER_DEPTHS[0]
PROSE_KIND = "prose"
ACTIVE_CRAFT = "ACTIVE"
POINT = "POINT"


@dataclass(frozen=True)
class _Located:
    locations: tuple[DistrictLocation, ...]
    craft_names: Mapping[uuid.UUID, str]
    sources: Mapping[str, dict[str, Any]]


async def district_records(
    session: AsyncSession, district_lgd: int, *, acls: Sequence[str] = OPEN_CHUNK_ACLS
) -> DistrictRecords | None:
    district = (await district_refs(session, [district_lgd])).get(district_lgd)
    boundary = (await dataset_records(session, {BOUNDARY_DATASET_CODE})).get(BOUNDARY_DATASET_CODE)
    if district is None or boundary is None:
        return None
    located = await _district_locations(session, district_lgd)
    values = await district_values(session, [district_lgd])
    stories = await district_story_pieces(session, district_lgd)
    prose = await _craft_prose(session, district, located.craft_names)
    states, cited = await claim_states(session, [*stories, *prose], acls=acls)
    usable = [piece for piece in [*stories, *prose] if _reusable(piece, states, cited.sources)]
    shown = _land_order(usable, located.craft_names)
    sources = {**located.sources, **cited.sources}
    return DistrictRecords(
        district=district,
        boundary=boundary,
        locations=located.locations,
        values=values,
        datasets=await dataset_records(session, {row.dataset_code for row in values}),
        blocks=tuple(_land_block(piece, ordinal) for ordinal, piece in enumerate(shown, start=1)),
        sources={source_id: SourceRef.model_validate(ref) for source_id, ref in sources.items()},
    )


async def _district_locations(session: AsyncSession, district_lgd: int) -> _Located:
    covers = exists().where(
        AdminDistrict.lgd == district_lgd,
        func.ST_Covers(AdminDistrict.geom, func.geometry(CraftLocation.geom)),
    )
    located = located_places(
        or_(CraftLocation.districtLgd == district_lgd, and_(CraftLocation.precision == POINT, covers))
    )
    statement = (
        select(located.c.id, located.c.role, located.c.evidenceLevel, Craft, Source)
        .select_from(located)
        .join(Craft, Craft.id == located.c.craftId)
        .join(Source, and_(Source.id == located.c.sourceId, Source.sensitivity != RESTRICTED_SENSITIVITY))
        .where(
            located.c.located_lgd == district_lgd,
            located.c.precision.in_(DISTRICT_PRECISIONS),
            Craft.status == ACTIVE_CRAFT,
            Craft.isCatchAll.is_(False),
        )
        .order_by(located.c.id)
    )
    rows = (await session.execute(statement)).tuples().all()
    locations = tuple(
        DistrictLocation(
            id=str(location_id),
            craft=CraftRef.model_validate(craft_ref(craft)),
            role=role,
            level=level,
            source_id=str(source.id),
            source_title=source.title,
        )
        for location_id, role, level, craft, source in rows
    )
    names = {craft.id: craft.name for _, _, _, craft, _ in rows}
    sources = {str(source.id): source_ref(source) for *_, source in rows}
    return _Located(locations, names, sources)


async def _craft_prose(
    session: AsyncSession, district: DistrictRef, craft_names: Mapping[uuid.UUID, str]
) -> list[KnowledgePiece]:
    if not craft_names:
        return []
    subject = district_subject(district.district_lgd)
    rows = await session.scalars(
        select(PieceRow)
        .where(
            PieceRow.craftId.in_(list(craft_names)),
            PieceRow.kind == PROSE_KIND,
            PieceRow.facet.in_(LAND_FACET_ORDER),
            PieceRow.topicKey.contains(subject, autoescape=True),
            PieceRow.language == CANONICAL_LANGUAGE,
            PieceRow.supersededById.is_(None),
            PieceRow.staleSince.is_(None),
            PieceRow.hiddenAt.is_(None),
        )
        .order_by(PieceRow.createdAt.desc(), PieceRow.id)
        .limit(PIECE_CANDIDATES_MAX)
    )
    return [piece for row in rows.all() if (piece := stored_piece(row)) and _names_subject(piece, subject)]


def _land_order(
    usable: Sequence[KnowledgePiece], craft_names: Mapping[uuid.UUID, str]
) -> list[KnowledgePiece]:
    stories = [piece for piece in usable if piece.craft_id is None][:1]
    newest = {
        (piece.craft_id, piece.facet): piece for piece in reversed(usable) if piece.craft_id is not None
    }
    return [*stories, *sorted(newest.values(), key=lambda piece: _prose_order(piece, craft_names))]


def _names_subject(piece: KnowledgePiece, subject: str) -> bool:
    return subject in piece.topic_key.split(":", 1)[1].split(SUBJECT_JOINER)


def _prose_order(piece: KnowledgePiece, craft_names: Mapping[uuid.UUID, str]) -> tuple[str, int]:
    name = craft_names.get(piece.craft_id, "") if piece.craft_id else ""
    return name.casefold(), LAND_FACET_ORDER.index(piece.facet)


def _reusable(
    piece: KnowledgePiece, states: Mapping[uuid.UUID, ClaimState], sources: Mapping[str, Any]
) -> bool:
    ask = ReuseAsk(craft_id=piece.craft_id, facet=piece.facet, topic_key=piece.topic_key, depth=SHALLOWEST)
    if reuse_refusal(piece, ask, visible_as_cited(piece, states)) is not None:
        return False
    return all(source_id in sources for source_id in piece.payload.cited_source_ids())


def _land_block(piece: KnowledgePiece, ordinal: int) -> Block:
    block_id = f"{LAND_BLOCK_PREFIX}{ordinal}"
    placed = placed_block(piece, block_id)
    counter = itertools.count(1)
    payload = with_payload_sentences(
        placed.model_dump(mode="json", by_alias=True),
        lambda sentence: {**sentence, "id": f"{block_id}.{next(counter)}"},
    )
    return type(placed).model_validate(payload)
