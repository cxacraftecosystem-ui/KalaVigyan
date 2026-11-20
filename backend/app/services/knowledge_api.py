from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.models import ArticleSection as SectionRow, Claim, Craft, Source
from app.models.enums import DISCIPLINES
from app.research.article_sections import ArticleSection
from app.research.coverage import FieldCoverage
from app.research.coverage_chapters import FIELD_CHAPTERS
from app.research.crafts import CraftRef
from app.research.knowledge_api import (
    FACTS_LIMIT_DEFAULT,
    CraftFacts,
    CraftSection,
    Fact,
    FactCitation,
    FactSource,
    FieldFacts,
    FieldInfo,
    FieldList,
    FieldSection,
)
from app.research.retrieval import OPEN_CHUNK_ACLS
from app.research.sections import DISCIPLINE_FIELDS, DISCIPLINE_TITLES
from app.research.vocabulary import LEVEL_ORDER

from . import knowledge_view
from .coverage import craft_coverage
from .coverage_reads import (
    FACT_TASK_KINDS,
    FIELD_TASK_KINDS,
    FactDetails,
    craft_field_work,
    fact_details,
)

__all__ = [
    "UNKNOWN_CRAFT",
    "craft_facts",
    "craft_section",
    "craft_sections",
    "every_fact",
    "field_list",
    "held_field_list",
    "known_craft",
]

UNKNOWN_CRAFT = "No craft has the slug {slug}; find_crafts gives the slugs."
PUBLIC_MODE = "HYBRID"
PUBLISHED = "PUBLISHED"
CRAFT_SUBJECT = "craft"
NO_DETAILS = FactDetails()


def field_list(coverage: FieldCoverage | None = None) -> FieldList:
    return FieldList(
        craft_slug=coverage.subject_slug if coverage is not None else None,
        fields=[
            FieldInfo(
                field=field,
                title=DISCIPLINE_TITLES[field],
                covers=DISCIPLINE_FIELDS[field],
                chapter=FIELD_CHAPTERS[field],
                held=coverage.count(field) if coverage is not None else None,
            )
            for field in DISCIPLINES
        ],
    )


async def held_field_list(session: AsyncSession, slug: str) -> FieldList:
    craft = await known_craft(session, slug)
    return field_list(await craft_coverage(session, craft.slug))


async def craft_facts(
    session: AsyncSession,
    slug: str,
    *,
    site: str,
    field: str | None = None,
    query: str | None = None,
    limit: int = FACTS_LIMIT_DEFAULT,
) -> CraftFacts:
    craft = await known_craft(session, slug)
    views, sources = await knowledge_view.claims_for(
        session, craft, mode=PUBLIC_MODE, question=query, acls=OPEN_CHUNK_ACLS
    )
    placed = await _claim_fields(session, [view.id for view in views])
    chosen = [view for view in views if field is None or field in placed[view.id]]
    ordered = (_ranked(chosen) if query else knowledge_view.order_claims(chosen))[:limit]
    details = await fact_details(session, [view.id for view in ordered])
    facts = [_fact(view, placed[view.id], details) for view in ordered]
    return CraftFacts(
        craft=_ref(craft),
        field=field,
        query=query,
        facts=facts,
        by_field=_by_field(placed, facts, field),
        open_work=await craft_field_work(session, craft, site=site, kinds=FACT_TASK_KINDS, field=field),
        sources=_cited_sources(facts, sources),
        page_url=f"{site}/crafts/{craft.slug}",
    )


async def every_fact(session: AsyncSession, craft: Craft) -> tuple[list[Fact], list[FactSource]]:
    views, sources = await knowledge_view.claims_for(session, craft, mode=PUBLIC_MODE, acls=OPEN_CHUNK_ACLS)
    placed = await _claim_fields(session, [view.id for view in views])
    facts = [_fact(view, placed[view.id], NO_DETAILS) for view in knowledge_view.order_claims(views)]
    return facts, _cited_sources(facts, sources)


def _cited_sources(facts: Sequence[Fact], sources: dict[uuid.UUID, Source]) -> list[FactSource]:
    cited = {citation.source_id for fact in facts for citation in fact.citations}
    return [_source(source) for source_id, source in sorted(sources.items()) if str(source_id) in cited]


async def craft_section(session: AsyncSession, slug: str, field: str, *, site: str) -> CraftSection:
    craft = await known_craft(session, slug)
    rows = await _published(session, craft, field)
    return CraftSection(
        craft=_ref(craft),
        field=field,
        section=_section(craft, rows[0]) if rows else None,
        open_work=await craft_field_work(session, craft, site=site, kinds=FIELD_TASK_KINDS, field=field),
        page_url=f"{site}/crafts/{craft.slug}",
    )


async def craft_sections(session: AsyncSession, slug: str, *, site: str) -> CraftSection:
    craft = await known_craft(session, slug)
    rows = await _published(session, craft, None)
    return CraftSection(
        craft=_ref(craft),
        field=None,
        section=None,
        sections=[_section(craft, row) for row in rows],
        by_field=[_field_section(row) for row in rows],
        open_work=await craft_field_work(session, craft, site=site, kinds=FIELD_TASK_KINDS),
        page_url=f"{site}/crafts/{craft.slug}",
    )


async def known_craft(session: AsyncSession, slug: str) -> Craft:
    craft = await knowledge_view.resolve_craft(session, slug)
    if craft is None:
        raise InvalidInput(UNKNOWN_CRAFT.format(slug=slug))
    return craft


async def _published(session: AsyncSession, craft: Craft, field: str | None) -> list[SectionRow]:
    query = select(SectionRow).where(SectionRow.craftId == craft.id, SectionRow.status == PUBLISHED)
    if field is not None:
        query = query.where(SectionRow.field == field)
    rows = list((await session.scalars(query)).all())
    order = {discipline: rank for rank, discipline in enumerate(DISCIPLINES)}
    return sorted(rows, key=lambda row: order.get(row.field, len(order)))


def _section(craft: Craft, row: SectionRow) -> ArticleSection:
    return ArticleSection(
        subject_kind=CRAFT_SUBJECT,
        subject_slug=craft.slug,
        field=row.field,
        version=row.version,
        status=row.status,
        sentences=row.sentences,
    )


def _field_section(row: SectionRow) -> FieldSection:
    claims = {str(claim) for sentence in row.sentences for claim in sentence.get("claimIds") or ()}
    return FieldSection(field=row.field, sentences=len(row.sentences), claims=len(claims))


def _by_field(
    placed: Mapping[uuid.UUID, list[str]], facts: Sequence[Fact], field: str | None
) -> list[FieldFacts]:
    wanted = [field] if field is not None else list(DISCIPLINES)
    counted = []
    for discipline in wanted:
        count = sum(1 for fields in placed.values() if discipline in fields)
        if count:
            shown = [fact.id for fact in facts if discipline in (fact.field, *fact.fields)]
            counted.append(FieldFacts(field=discipline, count=count, shown=shown))
    return counted


async def _claim_fields(session: AsyncSession, claim_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, list[str]]:
    if not claim_ids:
        return {}
    rows = await session.execute(
        select(Claim.id, Claim.field, Claim.fields).where(Claim.id.in_(list(claim_ids)))
    )
    return {
        claim_id: ([primary] if primary else []) + list(others) for claim_id, primary, others in rows.all()
    }


def _ranked(views: list[knowledge_view.ClaimView]) -> list[knowledge_view.ClaimView]:
    return sorted(
        views, key=lambda view: (-view.rank, LEVEL_ORDER.get(view.level, len(LEVEL_ORDER)), view.text)
    )


def _fact(view: knowledge_view.ClaimView, fields: list[str], details: FactDetails) -> Fact:
    return Fact(
        id=view.id,
        text=view.text,
        level=view.level,
        field=fields[0] if fields else None,
        fields=fields[1:],
        citations=[
            FactCitation(source_id=cite["sourceId"], quote=cite["quote"], locator=cite["locator"])
            for cite in view.citations
        ],
        quantity=details.quantities.get(view.id),
        readings=details.readings.get(view.id, []),
        figures=details.figures.get(view.id, []),
    )


def _source(source: Source) -> FactSource:
    shown = knowledge_view.source_ref(source)
    return FactSource(
        id=shown["id"],
        kind=shown["kind"],
        title=shown["title"],
        authors=shown["authors"],
        year=shown["year"],
        doi=shown["doi"],
        url=shown["url"],
        publisher=shown["publisher"],
        licence=shown["licence"],
        attribution=shown["attribution"],
    )


def _ref(craft: Craft) -> CraftRef:
    return CraftRef.model_validate(knowledge_view.craft_ref(craft))
