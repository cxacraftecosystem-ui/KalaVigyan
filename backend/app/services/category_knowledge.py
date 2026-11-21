from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import replace

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import ArticleSection as SectionRow, Claim, Source
from app.models.enums import DISCIPLINES
from app.research.knowledge_api import FACTS_LIMIT_DEFAULT, CraftFacts, CraftSection
from app.research.vocabulary import LEVEL_ORDER
from app.retrieval.statements import lexical_rank, text_query
from app.retrieval.text import or_tsquery

from . import knowledge_view
from .candidate_store import FactSubject, subject_claims
from .coverage_reads import FACT_TASK_KINDS, FIELD_TASK_KINDS, fact_details, subject_field_work
from .knowledge_api import (
    article_section,
    cited_sources,
    claim_fields,
    fact_of,
    facts_by_field,
    field_section,
    published_sections,
    ranked_views,
)
from .open_work_subjects import CATEGORY, WorkSubject

__all__ = ["category_facts", "category_sections"]

FIELD_ORDER = {discipline: rank for rank, discipline in enumerate(DISCIPLINES)}
Views = list[knowledge_view.ClaimView]


async def category_facts(
    session: AsyncSession,
    subject: WorkSubject,
    *,
    site: str,
    field: str | None = None,
    query: str | None = None,
    limit: int = FACTS_LIMIT_DEFAULT,
) -> CraftFacts:
    views, sources = await _held_views(session, subject, query)
    placed = await claim_fields(session, [view.id for view in views])
    chosen = [view for view in views if field is None or field in placed[view.id]]
    ordered = (ranked_views(chosen) if query else _in_field_order(chosen, placed))[:limit]
    details = await fact_details(session, [view.id for view in ordered])
    facts = [fact_of(view, placed[view.id], details) for view in ordered]
    page = subject.task_subject(site)
    return CraftFacts(
        subject=page,
        field=field,
        query=query,
        facts=facts,
        by_field=facts_by_field(placed, facts, field),
        open_work=await subject_field_work(session, subject, site=site, kinds=FACT_TASK_KINDS, field=field),
        sources=cited_sources(facts, sources),
        page_url=page.page_url,
    )


async def category_sections(
    session: AsyncSession, subject: WorkSubject, field: str | None, *, site: str
) -> CraftSection:
    rows = await published_sections(session, SectionRow.categoryId == subject.id, field)
    sections = [article_section(CATEGORY, subject.slug, row) for row in rows]
    page = subject.task_subject(site)
    return CraftSection(
        subject=page,
        field=field,
        section=(sections[0] if sections else None) if field is not None else None,
        sections=sections if field is None else [],
        by_field=[field_section(row) for row in rows] if field is None else [],
        open_work=await subject_field_work(session, subject, site=site, kinds=FIELD_TASK_KINDS, field=field),
        page_url=page.page_url,
    )


async def _held_views(
    session: AsyncSession, subject: WorkSubject, query: str | None
) -> tuple[Views, dict[uuid.UUID, Source]]:
    owner = FactSubject(kind=CATEGORY, name=subject.name, slug=subject.slug, category_id=subject.id)
    claim_ids = list(await session.scalars(select(Claim.id).where(subject_claims(owner))))
    found, sources = await knowledge_view.claims_by_id(session, claim_ids)
    ranks = await _ranks(session, list(found), query)
    return [replace(view, rank=ranks.get(view.id, 0.0)) for view in found.values()], sources


async def _ranks(
    session: AsyncSession, claim_ids: Sequence[uuid.UUID], query: str | None
) -> dict[uuid.UUID, float]:
    tsquery = or_tsquery(query or "")
    if not tsquery or not claim_ids:
        return {}
    rank = lexical_rank(Claim.tsv, text_query(tsquery))
    rows = await session.execute(select(Claim.id, rank).where(Claim.id.in_(list(claim_ids))))
    return {claim_id: float(value or 0) for claim_id, value in rows.all()}


def _in_field_order(views: Views, placed: Mapping[uuid.UUID, list[str]]) -> Views:
    def order(view: knowledge_view.ClaimView) -> tuple[int, int, str]:
        fields = placed.get(view.id) or [""]
        return (
            FIELD_ORDER.get(fields[0], len(FIELD_ORDER)),
            LEVEL_ORDER.get(view.level, len(LEVEL_ORDER)),
            view.text,
        )

    return sorted(views, key=order)
