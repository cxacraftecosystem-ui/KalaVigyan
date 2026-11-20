from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ArticleSection,
    Claim,
    Compound,
    Craft,
    CraftCategory,
    CraftSubCategory,
    CuratedCategoryClaim,
    KnowledgePiece,
    KnowledgePieceSubject as Subject,
)
from app.models.enums import DISCIPLINES
from app.research.component_specs_general_delivery import DeliveredComponent

from .component_library import library_components
from .component_places import PlaceBinding, component_binding, subject_place_keys
from .component_proposals_drawn import stored_delivery
from .craft_page_family import family_place, reader_name
from .knowledge_export import EXPORT_COMPONENTS_MAX
from .media_ref_store import stored_media_refs
from .monograph_generated_drawings import Drawings
from .monograph_generated_pictures import PlateSource, contributed_plates, curated_plate
from .monograph_generated_units import SubjectRecord
from .open_work_subjects import CATEGORY, WorkSubject
from .page_layouts_backfill import curated_pictures

__all__ = [
    "PlateSource",
    "RegisteredComponent",
    "StoredSection",
    "component_binding_of",
    "subject_components",
    "subject_pictures",
    "subject_record",
    "subject_sections",
]

PUBLISHED = "PUBLISHED"
CONCEPT_SUBJECT = "CONCEPT"
INLINE = "INLINE"
KICKER_SEPARATOR = " · "
PRACTICE_SEPARATOR = ", "
GI = "GI"
FIELD_ORDER = {field: n for n, field in enumerate(DISCIPLINES)}


@dataclass(frozen=True)
class StoredSection:
    field: str
    version: int
    sentences: tuple[Mapping[str, Any], ...]


@dataclass(frozen=True)
class RegisteredComponent:
    label: str
    kind: str
    title: str
    description: str
    field: str
    fields: tuple[str, ...]
    subjects: tuple[str, ...]
    monograph: str | None
    anchor: str | None
    delivered: DeliveredComponent | None = None
    borrowed: bool = False


def component_binding_of(component: RegisteredComponent, drawings: Drawings) -> PlaceBinding:
    if component.delivered is not None:
        texts = [unit.text for unit in component.delivered.units.values()]
    elif component.monograph is not None:
        texts = drawings.unit_texts(component.monograph, component.label)
    else:
        texts = []
    return component_binding(
        kind=component.kind,
        field=component.field,
        places=subject_place_keys(component.subjects),
        texts=[component.title, component.description, *texts],
    )


async def subject_sections(session: AsyncSession, subject: WorkSubject) -> list[StoredSection]:
    column = ArticleSection.categoryId if subject.kind == CATEGORY else ArticleSection.craftId
    rows = await session.scalars(
        select(ArticleSection).where(column == subject.id, ArticleSection.status == PUBLISHED)
    )
    found = [StoredSection(row.field, row.version, tuple(row.sentences)) for row in rows]
    return sorted(found, key=lambda section: FIELD_ORDER.get(section.field, len(FIELD_ORDER)))


async def subject_record(session: AsyncSession, subject: WorkSubject) -> SubjectRecord:
    if subject.kind == CATEGORY:
        family = family_place(subject.name, None).family
        return SubjectRecord(name=subject.name, kicker=family.label if family is not None else None)
    craft = await session.get(Craft, subject.id)
    if craft is None:
        return SubjectRecord(name=subject.name)
    names = (
        await session.execute(
            select(CraftCategory.name, CraftSubCategory.name)
            .join(CraftCategory, CraftCategory.id == CraftSubCategory.categoryId)
            .where(CraftSubCategory.id == craft.subCategoryId)
        )
    ).first()
    place = family_place(*(names or (craft.category, None)))
    kicker = KICKER_SEPARATOR.join(part.label for part in (place.family, place.kind) if part is not None)
    return SubjectRecord(
        name=reader_name(craft.slug, craft.name, catch_all=bool(craft.isCatchAll), kind=place.kind),
        kicker=kicker or None,
        place=PRACTICE_SEPARATOR.join(craft.stateOfPractice or ()) or None,
        gi=craft.giStatus == GI,
    )


async def subject_components(
    session: AsyncSession, subject: WorkSubject, claim_ids: Sequence[uuid.UUID]
) -> list[RegisteredComponent]:
    if subject.kind == CATEGORY:
        found = await _category_pieces(session, subject.id, claim_ids)
    else:
        listed = await library_components(session, slug=subject.slug, limit=EXPORT_COMPONENTS_MAX)
        labels = [component.label for component in listed.components]
        found = list(await session.scalars(select(KnowledgePiece).where(KnowledgePiece.label.in_(labels))))
    owner = None if subject.kind == CATEGORY else subject.id
    rows = [row for row in found if row.craftId is None or row.craftId == owner]
    subjects = await _subject_keys(session, [row.id for row in rows])
    return sorted(
        (_component(row, subjects.get(row.id, ()), owner) for row in rows if row.label is not None),
        key=lambda component: component.label,
    )


async def subject_pictures(session: AsyncSession, subject: WorkSubject) -> list[PlateSource]:
    pictures = await curated_pictures(session, subject)
    media = await stored_media_refs(session, [picture.media_ref_id for picture in pictures])
    curated = [
        curated_plate(picture, media[picture.media_ref_id])
        for picture in pictures
        if picture.media_ref_id in media and media[picture.media_ref_id].display == INLINE
    ]
    contributed = [] if subject.kind == CATEGORY else await contributed_plates(session, subject.id)
    return [*curated, *contributed]


async def _category_pieces(
    session: AsyncSession, category_id: uuid.UUID, claim_ids: Sequence[uuid.UUID]
) -> list[KnowledgePiece]:
    curated = await session.scalars(
        select(CuratedCategoryClaim.claimId).where(CuratedCategoryClaim.categoryId == category_id)
    )
    claims = list(dict.fromkeys([*curated.all(), *claim_ids]))
    if not claims:
        return []
    concepts = select(Claim.subjectId).where(Claim.id.in_(claims), Claim.subjectType == CONCEPT_SUBJECT)
    linked = select(Subject.pieceId).where(Subject.conceptId.in_(concepts))
    rows = await session.scalars(
        select(KnowledgePiece).where(
            KnowledgePiece.label.is_not(None),
            KnowledgePiece.hiddenAt.is_(None),
            KnowledgePiece.supersededById.is_(None),
            or_(KnowledgePiece.id.in_(linked), KnowledgePiece.claimIds.overlap(claims)),
        )
    )
    return list(rows.all())


async def _subject_keys(
    session: AsyncSession, piece_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, tuple[str, ...]]:
    if not piece_ids:
        return {}
    rows = await session.execute(
        select(Subject, Craft.slug, Compound.pubchemCid)
        .outerjoin(Craft, Craft.id == Subject.craftId)
        .outerjoin(Compound, Compound.id == Subject.compoundId)
        .where(Subject.pieceId.in_(list(piece_ids)))
        .order_by(Subject.pieceId, Subject.kind, Subject.createdAt)
    )
    found: dict[uuid.UUID, list[str]] = {}
    for subject, craft_slug, cid in rows.all():
        key = _subject_key(subject, craft_slug, cid)
        if key is not None:
            found.setdefault(subject.pieceId, []).append(key)
    return {piece_id: tuple(keys) for piece_id, keys in found.items()}


def _subject_key(subject: Subject, craft_slug: str | None, cid: int | None) -> str | None:
    if craft_slug is not None:
        return f"craft:{craft_slug}"
    if cid is not None:
        return f"compound:{cid}"
    if subject.placeKey is not None:
        return f"place:{subject.placeKey}"
    if subject.conceptId is not None:
        return f"concept:{subject.conceptId}"
    return None


def _component(
    row: KnowledgePiece, subjects: tuple[str, ...], owner: uuid.UUID | None
) -> RegisteredComponent:
    payload = row.payload if isinstance(row.payload, dict) else {}
    monograph = payload.get("monograph")
    anchor = payload.get("anchor")
    return RegisteredComponent(
        label=str(row.label),
        kind=row.kind,
        title=row.title or str(row.label),
        description=row.description or "",
        field=row.facet,
        fields=tuple(row.fields or ()),
        subjects=subjects,
        monograph=monograph if isinstance(monograph, str) else None,
        anchor=anchor if isinstance(anchor, str) else None,
        delivered=stored_delivery(str(row.label), payload),
        borrowed=row.craftId is None or row.craftId != owner,
    )
