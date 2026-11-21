from __future__ import annotations

import uuid
from collections.abc import Collection, Iterable, Sequence

from pydantic import Field
from sqlalchemy import ColumnElement, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.craft_master_loader import ACTIVE
from app.models import AdminDistrict, Compound, Concept, Craft, Material
from app.research.base import absent
from app.research.knowledge_api import ComponentSubject
from app.research.retrieval import VISIBLE_SENSITIVITY

from .page_keys import district_key
from .source_lookup_models import EntityRecord

__all__ = ["CONCEPTS_MAX", "HeldSubject", "compound_subjects", "entity_subjects"]

CONCEPTS_MAX = 10
DISTRICT_SUFFIX = " district"
COMPOUND_KIND, CONCEPT_KIND, CRAFT_KIND, PLACE_KIND = ("COMPOUND", "CONCEPT", "CRAFT", "PLACE")


class HeldSubject(ComponentSubject):
    record: str
    craft_slug: str | None = Field(default=None, exclude_if=absent)


async def compound_subjects(session: AsyncSession, cids: Collection[int]) -> list[HeldSubject]:
    if not cids:
        return []
    found: list[HeldSubject] = []
    held = await session.scalars(select(Compound).where(Compound.pubchemCid.in_(sorted(cids))))
    for compound in sorted(held, key=lambda row: row.pubchemCid or 0):
        record = str(compound.pubchemCid)
        found.append(HeldSubject(kind=COMPOUND_KIND, key=str(compound.id), name=compound.name, record=record))
        named = _folded([compound.name, *compound.synonyms])
        linked = select(Material.conceptId).where(Material.compoundId == compound.id)
        found += await _concepts(session, record, or_(Concept.id.in_(linked), _named(named)))
    return found


async def entity_subjects(session: AsyncSession, entities: Sequence[EntityRecord]) -> list[HeldSubject]:
    found: list[HeldSubject] = []
    for entity in entities:
        names = _folded([entity.label, entity.taxon_name])
        found += await _concepts(session, entity.qid, _named(names))
        found += await _crafts(session, entity.qid, names)
        found += await _districts(
            session, entity.qid, {*names, *(n.removesuffix(DISTRICT_SUFFIX) for n in names)}
        )
        found += [
            subject.model_copy(update={"record": entity.qid}) for subject in await _cid(session, entity)
        ]
    return list({(subject.kind, subject.key, subject.record): subject for subject in found}.values())


async def _cid(session: AsyncSession, entity: EntityRecord) -> list[HeldSubject]:
    cid = entity.pubchem_cid
    if cid is None or not cid.isdigit():
        return []
    return await compound_subjects(session, [int(cid)])


async def _concepts(session: AsyncSession, record: str, condition: ColumnElement[bool]) -> list[HeldSubject]:
    rows = await session.scalars(
        select(Concept)
        .where(condition, Concept.sensitivity == VISIBLE_SENSITIVITY)
        .order_by(Concept.craftId.is_not(None), Concept.subCategoryId.is_not(None), Concept.name, Concept.id)
        .limit(CONCEPTS_MAX)
    )
    concepts = list(rows)
    slugs = await _craft_slugs(
        session, {concept.craftId for concept in concepts if concept.craftId is not None}
    )
    return [
        HeldSubject(
            kind=CONCEPT_KIND,
            key=str(concept.id),
            name=concept.name,
            record=record,
            craft_slug=slugs.get(concept.craftId) if concept.craftId is not None else None,
        )
        for concept in concepts
    ]


async def _crafts(session: AsyncSession, record: str, names: Collection[str]) -> list[HeldSubject]:
    rows = await session.scalars(
        select(Craft)
        .where(func.lower(Craft.name).in_(sorted(names)), Craft.status == ACTIVE)
        .order_by(Craft.slug)
    )
    return [HeldSubject(kind=CRAFT_KIND, key=craft.slug, name=craft.name, record=record) for craft in rows]


async def _districts(session: AsyncSession, record: str, names: Collection[str]) -> list[HeldSubject]:
    rows = await session.scalars(
        select(AdminDistrict)
        .where(func.lower(AdminDistrict.name).in_(sorted(names)))
        .order_by(AdminDistrict.lgd)
    )
    return [
        HeldSubject(kind=PLACE_KIND, key=district_key(district.lgd), name=district.name, record=record)
        for district in rows
    ]


async def _craft_slugs(session: AsyncSession, craft_ids: Collection[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not craft_ids:
        return {}
    rows = await session.scalars(select(Craft).where(Craft.id.in_(sorted(craft_ids))))
    return {craft.id: craft.slug for craft in rows}


def _named(names: Collection[str]) -> ColumnElement[bool]:
    return func.lower(Concept.name).in_(sorted(names))


def _folded(names: Iterable[str | None]) -> set[str]:
    return {name.strip().lower() for name in names if name and name.strip()}
