from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.craft_master_loader import ACTIVE
from app.data.curation_scopes import is_family
from app.data.district_register import load_district_codes
from app.models import (
    Craft,
    CraftLocation,
    CraftSubCategory,
    KnowledgePiece,
    KnowledgePieceSubject as Subject,
)

from .component_places import PlaceBinding, PlacesHeld, component_binding, joined_places
from .measure_regions import district_states
from .open_work_subjects import CATEGORY, WorkSubject
from .region_records import located_places

__all__ = ["PieceFacts", "held_pieces", "piece_facts", "places_held", "subject_places"]


@dataclass(frozen=True)
class PieceFacts:
    id: uuid.UUID
    owner: uuid.UUID | None
    kind: str
    field: str
    title: str | None
    description: str | None


Pair = tuple[uuid.UUID, PieceFacts]


def piece_facts(piece: KnowledgePiece) -> PieceFacts:
    return PieceFacts(piece.id, piece.craftId, piece.kind, piece.facet, piece.title, piece.description)


async def subject_places(session: AsyncSession, subject: WorkSubject) -> PlacesHeld:
    if subject.kind == CATEGORY:
        members = await session.scalars(
            select(Craft.id)
            .join(CraftSubCategory, CraftSubCategory.id == Craft.subCategoryId)
            .where(CraftSubCategory.categoryId == subject.id, Craft.status == ACTIVE)
        )
        return joined_places((await _located(session, list(members.all()))).values())
    return (await places_held(session, [subject.id])).get(subject.id, PlacesHeld())


async def places_held(session: AsyncSession, craft_ids: Collection[uuid.UUID]) -> dict[uuid.UUID, PlacesHeld]:
    asked = list(dict.fromkeys(craft_ids))
    if not asked:
        return {}
    families = await _family_members(session, asked)
    located = await _located(session, [*asked, *(m for found in families.values() for m in found)])
    return {
        craft: joined_places(
            located.get(member, PlacesHeld()) for member in (craft, *families.get(craft, ()))
        )
        for craft in asked
    }


async def held_pieces(session: AsyncSession, pairs: Sequence[Pair]) -> set[tuple[uuid.UUID, uuid.UUID]]:
    if not pairs:
        return set()
    held = await places_held(session, {craft for craft, _ in pairs})
    places = await _piece_places(session, {piece.id for _, piece in pairs})
    return {
        (craft, piece.id)
        for craft, piece in pairs
        if piece.owner == craft or _bound(piece, places.get(piece.id, ())).held_by(held[craft])
    }


def _bound(piece: PieceFacts, places: Sequence[str]) -> PlaceBinding:
    texts = [piece.title or "", piece.description or ""]
    return component_binding(kind=piece.kind, field=piece.field, places=places, texts=texts)


async def _piece_places(
    session: AsyncSession, piece_ids: Collection[uuid.UUID]
) -> dict[uuid.UUID, list[str]]:
    rows = await session.execute(
        select(Subject.pieceId, Subject.placeKey).where(
            Subject.pieceId.in_(list(piece_ids)), Subject.placeKey.is_not(None)
        )
    )
    found: dict[uuid.UUID, list[str]] = defaultdict(list)
    for piece_id, key in rows.all():
        found[piece_id].append(str(key))
    return dict(found)


async def _family_members(
    session: AsyncSession, craft_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, list[uuid.UUID]]:
    rows = (
        await session.execute(
            select(Craft.id, Craft.subCategoryId, Craft.isCatchAll, Craft.stateOfPractice).where(
                Craft.id.in_(craft_ids)
            )
        )
    ).all()
    shelves = {row.id: row.subCategoryId for row in rows if row.subCategoryId is not None}
    families = [
        row.id
        for row in rows
        if row.id in shelves and is_family(bool(row.isCatchAll), row.stateOfPractice or ())
    ]
    if not families:
        return {}
    members = await session.execute(
        select(Craft.id, Craft.subCategoryId).where(
            Craft.subCategoryId.in_({shelves[family] for family in families}), Craft.status == ACTIVE
        )
    )
    on_shelf: dict[uuid.UUID, list[uuid.UUID]] = defaultdict(list)
    for member, shelf in members.all():
        on_shelf[shelf].append(member)
    return {family: [m for m in on_shelf[shelves[family]] if m != family] for family in families}


async def _located(session: AsyncSession, craft_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, PlacesHeld]:
    if not craft_ids:
        return {}
    practice = await _practised(session, craft_ids)
    located = located_places(CraftLocation.craftId.in_(list(dict.fromkeys(craft_ids))))
    rows = await session.execute(select(located.c.craftId, located.c.stateLgd, located.c.located_lgd))
    districts: dict[uuid.UUID, set[int]] = defaultdict(set)
    states: dict[uuid.UUID, set[int]] = defaultdict(set)
    for craft, state_lgd, district in rows.all():
        state = district_states().get(district, state_lgd) if district is not None else state_lgd
        practised = practice.get(craft, frozenset())
        if practised and state not in practised:
            continue
        if district is not None:
            districts[craft].add(district)
        if state is not None:
            states[craft].add(state)
    return {
        craft: PlacesHeld(
            frozenset(districts[craft]), frozenset(states[craft]) | practice.get(craft, frozenset())
        )
        for craft in dict.fromkeys(craft_ids)
    }


async def _practised(
    session: AsyncSession, craft_ids: Sequence[uuid.UUID]
) -> Mapping[uuid.UUID, frozenset[int]]:
    codes = load_district_codes()
    rows = await session.execute(select(Craft.id, Craft.stateOfPractice).where(Craft.id.in_(list(craft_ids))))
    return {
        craft: frozenset(lgd for name in names or () if (lgd := codes.state_lgd(name.strip())) is not None)
        for craft, names in rows.all()
    }
