from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from typing import Any

from sqlalchemy import ColumnElement, Select, cast, func, literal_column, or_, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import (
    ArticleSection,
    Claim,
    ClaimSource,
    Craft,
    CraftLocation,
    CraftSubCategory,
    CuratedCategory,
    CuratedCategoryClaim,
    KnowledgePiece,
    KnowledgePieceSubject,
    MediaRef,
    PageLayout,
    Source,
)
from app.research.monograph_document import MONOGRAPH_DOCUMENT_SCHEMA_VERSION

from .craft_page_stamp import Terms, count_term, counted_terms, plain_term, scalar_term, stamp_terms
from .open_work_subjects import CATEGORY, WorkSubject
from .page_code import page_code_fingerprint

__all__ = [
    "STORED_DOCUMENT_SCHEMA_VERSION",
    "document_stamp",
    "document_terms",
    "section_claims",
    "stamp_digest",
]

STORED_DOCUMENT_SCHEMA_VERSION = 1
PUBLISHED = "PUBLISHED"
PAGE_PREFIX = "page."
SENTENCE_CLAIMS = literal_column("'$[*].claimIds[*]'::jsonpath")


async def document_stamp(session: AsyncSession, subject: WorkSubject) -> str:
    own = (await session.execute(document_terms(subject))).one()
    terms = dict(own._mapping)
    if subject.kind != CATEGORY:
        craft = await session.get(Craft, subject.id)
        if craft is not None:
            page = (await session.execute(stamp_terms(craft))).one()
            terms |= {f"{PAGE_PREFIX}{key}": value for key, value in page._mapping.items()}
    return stamp_digest(
        terms, code=page_code_fingerprint(), site=get_settings().public_web_url, subject=_named(subject)
    )


def stamp_digest(terms: Mapping[str, Any], *, code: str, site: str, subject: str) -> str:
    record = {
        "code": code,
        "site": site,
        "schemaVersion": STORED_DOCUMENT_SCHEMA_VERSION,
        "documentSchemaVersion": MONOGRAPH_DOCUMENT_SCHEMA_VERSION,
        "subject": subject,
        "terms": {key: plain_term(value) for key, value in sorted(terms.items())},
    }
    text = json.dumps(record, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def document_terms(subject: WorkSubject) -> Select[Any]:
    category = subject.kind == CATEGORY
    owned = ArticleSection.categoryId == subject.id if category else ArticleSection.craftId == subject.id
    laid = PageLayout.categoryId == subject.id if category else PageLayout.craftId == subject.id
    cited = section_claims(owned)
    claims = Claim.id.in_(cited)
    if category:
        claims = or_(claims, Claim.id.in_(_curated_claims(subject.id)))
    terms: Terms = {
        **counted_terms("sections", ArticleSection.id, ArticleSection.updatedAt, owned),
        "sectionVersions": scalar_term(func.sum(ArticleSection.version), owned),
        "layouts": count_term(PageLayout.id, laid),
        "layoutVersion": scalar_term(func.max(PageLayout.version), laid),
        **_claim_terms(claims),
        **_shared_terms(),
    }
    if category:
        terms |= _category_terms(subject.id)
    return select(*(value.label(key) for key, value in terms.items()))


def section_claims(owned: ColumnElement[bool]) -> Select[Any]:
    listed = func.jsonb_path_query_array(ArticleSection.sentences, SENTENCE_CLAIMS)
    return select(cast(func.jsonb_array_elements_text(listed), UUID(as_uuid=True))).where(
        owned, ArticleSection.status == PUBLISHED
    )


def _claim_terms(claims: ColumnElement[bool]) -> Terms:
    named = select(Claim.id).where(claims)
    cited = select(ClaimSource.sourceId).where(ClaimSource.claimId.in_(named))
    return {
        **counted_terms("documentClaims", Claim.id, Claim.updatedAt, claims),
        **counted_terms(
            "documentCitations", ClaimSource.id, ClaimSource.updatedAt, ClaimSource.claimId.in_(named)
        ),
        **counted_terms("documentSources", Source.id, Source.updatedAt, Source.id.in_(cited)),
    }


def _shared_terms() -> Terms:
    return {
        **counted_terms(
            "components", KnowledgePiece.id, KnowledgePiece.updatedAt, KnowledgePiece.label.is_not(None)
        ),
        **counted_terms(
            "componentSubjects",
            KnowledgePieceSubject.id,
            KnowledgePieceSubject.createdAt,
            KnowledgePieceSubject.id.is_not(None),
        ),
        **counted_terms("pictureRecords", MediaRef.id, MediaRef.updatedAt, MediaRef.id.is_not(None)),
    }


def _category_terms(category_id: uuid.UUID) -> Terms:
    shelves = select(CraftSubCategory.id).where(CraftSubCategory.categoryId == category_id)
    members = select(Craft.id).where(Craft.subCategoryId.in_(shelves))
    curated = CuratedCategory.categoryId == category_id
    return {
        "curatedVersion": scalar_term(CuratedCategory.version, curated),
        "curatedAt": scalar_term(CuratedCategory.updatedAt, curated),
        **counted_terms(
            "curatedClaims",
            CuratedCategoryClaim.claimId,
            CuratedCategoryClaim.updatedAt,
            CuratedCategoryClaim.categoryId == category_id,
        ),
        **counted_terms(
            "shelves", CraftSubCategory.id, CraftSubCategory.updatedAt, CraftSubCategory.id.in_(shelves)
        ),
        **counted_terms("members", Craft.id, Craft.updatedAt, Craft.id.in_(members)),
        **counted_terms(
            "memberPlaces", CraftLocation.id, CraftLocation.updatedAt, CraftLocation.craftId.in_(members)
        ),
    }


def _curated_claims(category_id: uuid.UUID) -> Select[Any]:
    return select(CuratedCategoryClaim.claimId).where(CuratedCategoryClaim.categoryId == category_id)


def _named(subject: WorkSubject) -> str:
    return f"{subject.kind}:{subject.slug}"
