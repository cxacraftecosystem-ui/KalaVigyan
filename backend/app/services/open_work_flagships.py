from __future__ import annotations

import uuid
from collections import defaultdict
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ArticleSection,
    Claim,
    CuratedCategoryClaim,
    KnowledgePiece,
    KnowledgePieceSubject as Subject,
    PageLayout,
)
from app.research.page_layout import is_component_ref

from .component_library_applies import registered_pieces

__all__ = ["category_component_kinds"]

CONCEPT_SUBJECT = "CONCEPT"
PUBLISHED = "PUBLISHED"
REF_KEY = "ref"
CLAIMS_KEY = "claimIds"

Claims = dict[uuid.UUID, set[uuid.UUID]]


async def category_component_kinds(
    session: AsyncSession, category_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, frozenset[str]]:
    if not category_ids:
        return {}
    page_claims = await _page_claims(session, category_ids)
    held = {claim for claims in page_claims.values() for claim in claims}
    by_claim = await _claim_kinds(session, held)
    found: dict[uuid.UUID, set[str]] = defaultdict(set)
    for owner, claims in page_claims.items():
        found[owner].update(kind for claim in claims for kind in by_claim.get(claim, ()))
    for owner, kinds in (await _laid_out(session, category_ids)).items():
        found[owner] |= kinds
    return {owner: frozenset(kinds) for owner, kinds in found.items() if kinds}


async def _page_claims(session: AsyncSession, category_ids: Sequence[uuid.UUID]) -> Claims:
    found: Claims = defaultdict(set)
    curated = await session.execute(
        select(CuratedCategoryClaim.categoryId, CuratedCategoryClaim.claimId).where(
            CuratedCategoryClaim.categoryId.in_(list(category_ids))
        )
    )
    for owner, claim in curated.all():
        found[owner].add(claim)
    sections = await session.execute(
        select(ArticleSection.categoryId, ArticleSection.sentences).where(
            ArticleSection.categoryId.in_(list(category_ids)), ArticleSection.status == PUBLISHED
        )
    )
    for owner, sentences in sections.all():
        if owner is not None:
            found[owner] |= _cited(sentences)
    return dict(found)


async def _claim_kinds(session: AsyncSession, claims: set[uuid.UUID]) -> dict[uuid.UUID, set[str]]:
    if not claims:
        return {}
    wanted = sorted(claims)
    found: dict[uuid.UUID, set[str]] = defaultdict(set)
    resting = await session.execute(
        select(KnowledgePiece.kind, KnowledgePiece.claimIds).where(
            KnowledgePiece.claimIds.overlap(wanted), *registered_pieces()
        )
    )
    for kind, rests_on in resting.all():
        for claim in claims.intersection(rests_on or ()):
            found[claim].add(str(kind))
    keyed = await session.execute(
        select(Claim.id, KnowledgePiece.kind)
        .join(Subject, Subject.conceptId == Claim.subjectId)
        .join(KnowledgePiece, KnowledgePiece.id == Subject.pieceId)
        .where(Claim.id.in_(wanted), Claim.subjectType == CONCEPT_SUBJECT, *registered_pieces())
    )
    for claim, kind in keyed.all():
        found[claim].add(str(kind))
    return dict(found)


async def _laid_out(session: AsyncSession, category_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, set[str]]:
    rows = await session.execute(
        select(PageLayout.categoryId, PageLayout.entries)
        .where(PageLayout.categoryId.in_(list(category_ids)))
        .distinct(PageLayout.categoryId)
        .order_by(PageLayout.categoryId, PageLayout.version.desc())
    )
    placed = {owner: _component_refs(entries) for owner, entries in rows.all() if owner is not None}
    kinds = await _label_kinds(session, {label for labels in placed.values() for label in labels})
    return {owner: {kinds[label] for label in labels if label in kinds} for owner, labels in placed.items()}


async def _label_kinds(session: AsyncSession, labels: Iterable[str]) -> Mapping[str, str]:
    wanted = sorted(set(labels))
    if not wanted:
        return {}
    rows = await session.execute(
        select(KnowledgePiece.label, KnowledgePiece.kind).where(
            KnowledgePiece.label.in_(wanted), *registered_pieces()
        )
    )
    return {str(label): str(kind) for label, kind in rows.all()}


def _cited(sentences: Any) -> set[uuid.UUID]:
    if not isinstance(sentences, list):
        return set()
    cited = (claim for s in sentences if isinstance(s, dict) for claim in s.get(CLAIMS_KEY) or ())
    return {uuid.UUID(str(claim)) for claim in cited}


def _component_refs(entries: Any) -> set[str]:
    if not isinstance(entries, list):
        return set()
    refs = (entry.get(REF_KEY) for entry in entries if isinstance(entry, dict))
    return {ref for ref in refs if isinstance(ref, str) and is_component_ref(ref)}
