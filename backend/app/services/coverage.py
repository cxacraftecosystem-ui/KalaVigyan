from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import CTE, any_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.curation.limits import DISCIPLINE_CLAIMS_MIN
from app.models import (
    ArticleSection,
    ClaimSource,
    CraftGiRecord,
    CuratedCategory,
    CuratedCategoryClaim,
    CuratedCraft,
    KnowledgePiece,
    Source,
)
from app.research.coverage import (
    STRUCTURE_FIELDS,
    CoverageSubject,
    FieldCoverage,
    Holdings,
    MonographCoverage,
    field_coverage,
    held_fields,
)
from app.research.retrieval import RESTRICTED_SENSITIVITY

from . import knowledge_view
from .open_work_components import craft_pieces, registered_pieces
from .open_work_counts import Owners, owned_facts
from .open_work_subjects import (
    CATEGORY,
    WorkSubject,
    craft_subject,
    curated_craft_subjects,
    subject_by_key,
)

__all__ = [
    "COVERAGE_CLAIMS_MIN",
    "HeldFields",
    "category_coverage",
    "coverage_of",
    "craft_coverage",
    "held_field_lookup",
    "monograph_coverage",
    "owners_of",
    "subject_coverage",
    "subject_holdings",
]

COVERAGE_CLAIMS_MIN = DISCIPLINE_CLAIMS_MIN
PUBLISHED = "PUBLISHED"
COMMUNITIES = "communities"
COMMUNITY_CLAIMS = "claimIds"
SOCIETY = STRUCTURE_FIELDS[COMMUNITIES]
POLICY = STRUCTURE_FIELDS["gi"]

HeldFields = Callable[[str], Awaitable[tuple[str, ...]]]
ByOwner = dict[uuid.UUID, dict[str, set[str]]]


@dataclass(frozen=True)
class _Held:
    filed: Mapping[uuid.UUID, Mapping[str, frozenset[str]]]
    sources: ByOwner
    structure: ByOwner
    sections: Mapping[uuid.UUID, Mapping[str, int]]
    figures: ByOwner

    def owners(self) -> set[uuid.UUID]:
        return {*self.filed, *self.structure, *self.sections, *self.figures}

    def of(self, owner: uuid.UUID) -> Holdings:
        return Holdings(
            filed=dict(self.filed.get(owner, {})),
            sources=_frozen(self.sources.get(owner, {})),
            structure=_frozen(self.structure.get(owner, {})),
            sections=dict(self.sections.get(owner, {})),
            figures=_frozen(self.figures.get(owner, {})),
        )


async def subject_coverage(
    session: AsyncSession, subjects: Sequence[WorkSubject]
) -> dict[uuid.UUID, FieldCoverage]:
    if not subjects:
        return {}
    held = await subject_holdings(session, owners_of(subjects))
    return {
        subject.id: field_coverage(
            CoverageSubject(subject.kind, subject.slug, subject.name),
            held.get(subject.id, Holdings()),
            claims_min=COVERAGE_CLAIMS_MIN,
        )
        for subject in subjects
    }


async def coverage_of(session: AsyncSession, subject: WorkSubject) -> FieldCoverage:
    return (await subject_coverage(session, [subject]))[subject.id]


async def craft_coverage(session: AsyncSession, slug: str) -> FieldCoverage:
    return await coverage_of(session, await craft_subject(session, slug))


async def category_coverage(session: AsyncSession, slug: str) -> FieldCoverage:
    return await coverage_of(session, await subject_by_key(session, CATEGORY, slug))


async def monograph_coverage(session: AsyncSession) -> MonographCoverage:
    subjects = sorted(await curated_craft_subjects(session), key=lambda subject: subject.slug)
    found = await subject_coverage(session, subjects)
    return MonographCoverage(crafts=[found[subject.id] for subject in subjects])


def owners_of(subjects: Sequence[WorkSubject]) -> Owners:
    return Owners(
        crafts=tuple(subject.id for subject in subjects if subject.kind != CATEGORY),
        categories=tuple(subject.id for subject in subjects if subject.kind == CATEGORY),
    )


async def subject_holdings(session: AsyncSession, owners: Owners) -> dict[uuid.UUID, Holdings]:
    filed, sources = await _cited_claims(session, owned_facts(owners))
    held = _Held(
        filed=filed,
        sources=sources,
        structure=await _structure(session, owners),
        sections=await _sections(session, owners),
        figures=await _figures(session, owners),
    )
    return {owner: held.of(owner) for owner in held.owners()}


def held_field_lookup(sessions: async_sessionmaker[AsyncSession]) -> HeldFields:
    async def held(slug: str) -> tuple[str, ...]:
        async with sessions() as session:
            craft = await knowledge_view.resolve_craft(session, slug)
            if craft is None:
                return ()
            return held_fields(await craft_coverage(session, craft.slug))

    return held


async def _cited_claims(
    session: AsyncSession, owned: CTE
) -> tuple[dict[uuid.UUID, dict[str, frozenset[str]]], ByOwner]:
    rows = await session.execute(
        select(owned.c.owner, owned.c.claim, owned.c.field, owned.c.fields, ClaimSource.sourceId)
        .join(ClaimSource, ClaimSource.claimId == owned.c.claim)
        .join(Source, Source.id == ClaimSource.sourceId)
        .where(Source.sensitivity != RESTRICTED_SENSITIVITY)
    )
    filed: dict[uuid.UUID, dict[str, frozenset[str]]] = defaultdict(dict)
    sources: ByOwner = defaultdict(lambda: defaultdict(set))
    for owner, claim, primary, others, source in rows.all():
        filed[owner][str(claim)] = frozenset(f for f in (primary, *(others or ())) if f)
        sources[owner][str(claim)].add(str(source))
    return dict(filed), dict(sources)


async def _structure(session: AsyncSession, owners: Owners) -> ByOwner:
    found: ByOwner = defaultdict(lambda: defaultdict(set))
    if owners.crafts:
        records = await session.execute(
            select(CraftGiRecord.craftId, CraftGiRecord.claimIds).where(
                CraftGiRecord.craftId.in_(list(owners.crafts))
            )
        )
        for owner, claims in records.all():
            found[owner][POLICY].update(str(claim) for claim in claims or ())
    for owner, groups in await _communities(session, owners):
        found[owner][SOCIETY].update(_community_claims(groups))
    return dict(found)


async def _communities(session: AsyncSession, owners: Owners) -> list[tuple[uuid.UUID, Any]]:
    crafts = await _community_rows(session, CuratedCraft.craftId, CuratedCraft.page, owners.crafts)
    categories = await _community_rows(
        session, CuratedCategory.categoryId, CuratedCategory.page, owners.categories
    )
    return [*crafts, *categories]


async def _community_rows(
    session: AsyncSession, key: Any, page: Any, ids: Sequence[uuid.UUID]
) -> list[tuple[uuid.UUID, Any]]:
    if not ids:
        return []
    rows = await session.execute(select(key, page[COMMUNITIES]).where(key.in_(list(ids))))
    return [(owner, groups) for owner, groups in rows.all()]


def _community_claims(groups: Any) -> set[str]:
    if not isinstance(groups, list):
        return set()
    return {
        str(claim)
        for group in groups
        if isinstance(group, dict)
        for claim in group.get(COMMUNITY_CLAIMS) or ()
    }


async def _sections(session: AsyncSession, owners: Owners) -> dict[uuid.UUID, dict[str, int]]:
    rows = await session.execute(
        select(
            func.coalesce(ArticleSection.craftId, ArticleSection.categoryId),
            ArticleSection.field,
            func.jsonb_array_length(ArticleSection.sentences),
        ).where(
            ArticleSection.status == PUBLISHED,
            or_(ArticleSection.craftId.in_(owners.crafts), ArticleSection.categoryId.in_(owners.categories)),
        )
    )
    found: dict[uuid.UUID, dict[str, int]] = defaultdict(dict)
    for owner, discipline, sentences in rows.all():
        found[owner][discipline] = int(sentences)
    return dict(found)


async def _figures(session: AsyncSession, owners: Owners) -> ByOwner:
    found: ByOwner = defaultdict(lambda: defaultdict(set))
    for piece in await craft_pieces(session, owners.crafts):
        for discipline in piece.filed_under():
            found[piece.craft_id][discipline].add(piece.label)
    if owners.categories:
        rows = await session.execute(
            select(
                CuratedCategoryClaim.categoryId,
                KnowledgePiece.label,
                KnowledgePiece.facet,
                KnowledgePiece.fields,
            )
            .join(KnowledgePiece, CuratedCategoryClaim.claimId == any_(KnowledgePiece.claimIds))
            .where(CuratedCategoryClaim.categoryId.in_(list(owners.categories)), *registered_pieces())
            .distinct()
        )
        for owner, label, facet, fields in rows.all():
            for discipline in (facet, *(fields or ())):
                found[owner][discipline].add(str(label))
    return dict(found)


def _frozen(by_key: Mapping[str, set[str]]) -> dict[str, frozenset[str]]:
    return {key: frozenset(values) for key, values in by_key.items()}
