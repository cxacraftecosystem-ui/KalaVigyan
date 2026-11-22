from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from sqlalchemy import ColumnElement, Select, and_, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, defer

from app.models import (
    Claim,
    ClaimSource,
    Concept,
    ConceptEdge,
    CraftCategory,
    CuratedCategoryClaim,
    Source,
)
from app.research.retrieval import (
    OPEN_CHUNK_ACLS,
    RESTRICTED_SENSITIVITY,
    SHOWN_CLAIM_STATUSES,
    VISIBLE_SENSITIVITY,
)
from app.retrieval.citation_access import readable_citation
from app.retrieval.field_scope import withheld_field_sources

from .claim_holds import held_claim
from .open_data_crafts import NO_PLACE, CraftLookup, Placement
from .open_data_values import Row, day_of, number_of, stamp_of, text_of

__all__ = ["FIELD_TESTIMONY", "PublishedFacts", "published_facts"]

FIELD_TESTIMONY = "FIELD_TESTIMONY"
CONCEPT_SUBJECT = "CONCEPT"
EDGE_SUBJECT = "EDGE"
WEB_SCHEMES = ("https://", "http://")

_direct = aliased(Concept)
_edge = aliased(ConceptEdge)
_from = aliased(Concept)
_to = aliased(Concept)


@dataclass(frozen=True)
class PublishedFacts:
    claims: list[Row]
    citations: list[Row]
    sources: list[Row]

    def claim_ids(self) -> set[str]:
        return {row["id"] for row in self.claims}


async def published_facts(
    session: AsyncSession, lookup: CraftLookup, within: Sequence[ColumnElement[bool]] = ()
) -> PublishedFacts:
    categories = await _category_claims(session)
    statement = _published(select(Claim, _direct, _from, _to), within).options(
        defer(Claim.embedding), defer(Claim.tsv)
    )
    rows = (await session.execute(statement)).all()
    claims = [
        _claim_row(claim, _subject(direct, start, end), lookup, categories)
        for claim, direct, start, end in rows
    ]
    cites = (await session.scalars(_citations(within, ClaimSource))).all()
    cited = _citations(within, ClaimSource.sourceId)
    sources = (await session.scalars(select(Source).where(Source.id.in_(cited)))).all()
    return PublishedFacts(
        claims=sorted(claims, key=lambda row: row["id"]),
        citations=sorted(
            (_citation_row(cite) for cite in cites), key=lambda row: (row["claim_id"], row["id"])
        ),
        sources=sorted((_source_row(source) for source in sources), key=lambda row: row["id"]),
    )


def _published(statement: Select[Any], within: Sequence[ColumnElement[bool]]) -> Select[Any]:
    joined = (
        statement.outerjoin(
            _direct, and_(Claim.subjectType == CONCEPT_SUBJECT, _direct.id == Claim.subjectId)
        )
        .outerjoin(_edge, and_(Claim.subjectType == EDGE_SUBJECT, _edge.id == Claim.subjectId))
        .outerjoin(_from, _from.id == _edge.srcId)
        .outerjoin(_to, _to.id == _edge.dstId)
    )
    return joined.where(
        Claim.status.in_(SHOWN_CLAIM_STATUSES),
        Claim.sensitivity == VISIBLE_SENSITIVITY,
        or_(
            _direct.sensitivity == VISIBLE_SENSITIVITY,
            _from.sensitivity == VISIBLE_SENSITIVITY,
            _to.sensitivity == VISIBLE_SENSITIVITY,
        ),
        ~held_claim(),
        exists().where(ClaimSource.claimId == Claim.id, *_exportable_citation()),
        *within,
    )


def _citations(within: Sequence[ColumnElement[bool]], *columns: Any) -> Select[Any]:
    published = _published(select(Claim.id), within)
    return select(*columns).where(ClaimSource.claimId.in_(published), *_exportable_citation())


def _exportable_citation() -> list[ColumnElement[bool]]:
    open_sources = (
        select(Source.id)
        .where(Source.sensitivity != RESTRICTED_SENSITIVITY, Source.kind != FIELD_TESTIMONY)
        .correlate(None)
    )
    return [
        readable_citation(OPEN_CHUNK_ACLS),
        ClaimSource.sourceId.in_(open_sources),
        ClaimSource.sourceId.not_in(withheld_field_sources()),
    ]


async def _category_claims(session: AsyncSession) -> dict[uuid.UUID, str]:
    rows = await session.execute(
        select(CuratedCategoryClaim.claimId, CraftCategory.slug).join(
            CraftCategory, CraftCategory.id == CuratedCategoryClaim.categoryId
        )
    )
    return dict(rows.tuples().all())


def _subject(direct: Concept | None, start: Concept | None, end: Concept | None) -> tuple[Concept, bool]:
    if direct is not None:
        return direct, False
    shown = start if start is not None and start.sensitivity == VISIBLE_SENSITIVITY else end
    if shown is None:
        raise ValueError("a published relation names no visible concept")
    return shown, True


def _placement(concept: Concept, lookup: CraftLookup) -> Placement:
    if concept.craftId is not None:
        return lookup.of_craft(concept.craftId)
    if concept.subCategoryId is not None:
        return lookup.of_family(concept.subCategoryId)
    return NO_PLACE


def _claim_row(
    claim: Claim, subject: tuple[Concept, bool], lookup: CraftLookup, categories: Mapping[uuid.UUID, str]
) -> Row:
    concept, relation = subject
    craft, family, category = _placement(concept, lookup)
    return {
        "id": str(claim.id),
        "text": claim.text,
        "language": claim.textLang,
        "field": claim.field,
        "fields": list(claim.fields or []),
        "level": claim.evidenceLevel,
        "status": claim.status,
        "subject_kind": concept.type,
        "subject": concept.name,
        "relation": relation,
        "craft": craft,
        "family": family,
        "category": category or categories.get(claim.id),
        "value": number_of(claim.valueNum),
        "unit": text_of(claim.valueUnit),
        "sources_differ": bool(claim.sourcesDiffer),
        "version": claim.version,
        "supersedes": str(claim.supersedesId) if claim.supersedesId is not None else None,
        "created": stamp_of(claim.createdAt),
    }


def _citation_row(cite: ClaimSource) -> Row:
    return {
        "id": str(cite.id),
        "claim_id": str(cite.claimId),
        "source_id": str(cite.sourceId),
        "locator": text_of(cite.locator),
        "relation": cite.relation,
        "quoted": cite.quote is not None,
        "quote_check": cite.quoteCheck,
        "retrieved": day_of(cite.retrievedAt),
    }


def _source_row(source: Source) -> Row:
    external = source.externalIds or {}
    return {
        "id": str(source.id),
        "kind": source.kind,
        "title": source.title,
        "authors": _authors(source.authors),
        "publisher": text_of(source.publisher),
        "year": source.year,
        "doi": text_of(source.doi),
        "url": source.url if source.url and source.url.startswith(WEB_SCHEMES) else None,
        "archived_url": text_of(external.get("archivedUrl")),
        "language": text_of(external.get("language")),
        "access": text_of(external.get("access")),
        "grade": source.reliability,
        "licence": text_of(source.licence),
        "attribution": text_of(source.attribution),
        "retrieved": day_of(source.retrievedAt),
    }


def _authors(authors: Any) -> list[str]:
    named = (
        str(author.get("name") or "") if isinstance(author, dict) else str(author) for author in authors or []
    )
    return [name.strip() for name in named if name.strip()]
