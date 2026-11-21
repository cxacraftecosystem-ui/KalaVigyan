from __future__ import annotations

from typing import Any

from sqlalchemy import Select, and_, case, func, select

from app.models import (
    Claim,
    Concept,
    ConceptEdge,
    Craft,
    CraftCategory,
    CraftSubCategory,
    CuratedCategoryClaim,
)

from .text import context_title, document_text

__all__ = ["CONCEPT_SUBJECT", "EDGE_SUBJECT", "claim_document", "titled_claims"]

CONCEPT_SUBJECT = "CONCEPT"
EDGE_SUBJECT = "EDGE"


def titled_claims() -> Select[Any]:
    subject = case(
        (Claim.subjectType == CONCEPT_SUBJECT, Claim.subjectId),
        (Claim.subjectType == EDGE_SUBJECT, ConceptEdge.srcId),
    )
    owner = func.coalesce(Craft.name, CraftSubCategory.name, _marked_category(), _named_category())
    return (
        select(Claim.id, Claim.text, owner.label("owner"), Concept.name.label("concept"), Claim.field)
        .select_from(Claim)
        .outerjoin(ConceptEdge, and_(Claim.subjectType == EDGE_SUBJECT, ConceptEdge.id == Claim.subjectId))
        .outerjoin(Concept, Concept.id == subject)
        .outerjoin(Craft, Craft.id == Concept.craftId)
        .outerjoin(CraftSubCategory, CraftSubCategory.id == Concept.subCategoryId)
    )


def claim_document(row: Any) -> str:
    return document_text(row.text, title=context_title(row.owner, row.concept, row.field))


def _marked_category() -> Any:
    return (
        select(CraftCategory.name)
        .join(CuratedCategoryClaim, CuratedCategoryClaim.categoryId == CraftCategory.id)
        .where(CuratedCategoryClaim.claimId == Claim.id)
        .order_by(CraftCategory.name)
        .limit(1)
        .scalar_subquery()
    )


def _named_category() -> Any:
    return (
        select(CraftCategory.name)
        .where(func.lower(CraftCategory.name) == func.lower(Concept.name))
        .order_by(CraftCategory.name)
        .limit(1)
        .scalar_subquery()
    )
