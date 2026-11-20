from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from typing import Any

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models import Claim, ComponentProposal, Source
from app.research.component_specs_general_delivery import DeliveredComponent, delivered_claim_ids
from app.research.coverage_chapters import field_chapter
from app.research.monograph_document import MonographDocument
from app.research.monograph_page import CitedSource, ComponentEntry, LayoutEntry, MonographContent, TextUnit
from app.research.review_queue_delivery import (
    DeliveredFact,
    DeliveredReview,
    DeliveredUnitReview,
    PlacedDelivery,
)

from . import knowledge_view
from .component_proposals_drawn import drawn_delivery
from .knowledge_view import ClaimView
from .monograph_generated_units import DraftUnit, SourceBook, cited_unit, stored_source
from .page_preview_parts import SUBJECT_PREFIXES
from .review_queue_fact_views import fact_sources

__all__ = ["delivered_review", "placed_deliveries"]

PENDING = "PENDING"
DOCUMENT_VERSION = 1
SHARED_SUBJECT = "shared"
CRAFT_PATH = "/crafts/{slug}"


async def delivered_review(
    session: AsyncSession, row: ComponentProposal, craft_slug: str | None
) -> DeliveredReview | None:
    if row.spec is None or row.units is None:
        return None
    site = get_settings().public_web_url.rstrip("/")
    page_url = site + CRAFT_PATH.format(slug=craft_slug) if craft_slug else site
    delivered = DeliveredComponent.model_validate({"spec": row.spec, "units": row.units})
    claim_ids = delivered_claim_ids(delivered.units)
    visible, sources = await knowledge_view.claims_by_id(session, claim_ids)
    units = [
        DeliveredUnitReview(unit=ref, text=unit.text, claim_ids=list(unit.claim_ids))
        for ref, unit in sorted(delivered.units.items())
    ]
    return DeliveredReview(
        drawing=_drawing(row, delivered, visible, sources, (craft_slug, page_url)),
        units=units,
        facts=await _facts(session, claim_ids, visible),
    )


async def placed_deliveries(
    session: AsyncSession, proposer_id: uuid.UUID | None, refs: Sequence[str], craft_slug: str | None
) -> list[PlacedDelivery]:
    if proposer_id is None or not refs:
        return []
    rows = await session.scalars(
        select(ComponentProposal)
        .where(
            ComponentProposal.label.in_(list(refs)),
            ComponentProposal.proposerId == proposer_id,
            ComponentProposal.status == PENDING,
            ComponentProposal.spec.is_not(None),
        )
        .order_by(ComponentProposal.label)
    )
    placed: list[PlacedDelivery] = []
    for row in rows.all():
        delivery = await delivered_review(session, row, craft_slug)
        if delivery is not None:
            placed.append(PlacedDelivery(label=row.label, title=row.title, kind=row.kind, delivery=delivery))
    return placed


def _drawing(
    row: ComponentProposal,
    delivered: DeliveredComponent,
    visible: Mapping[uuid.UUID, ClaimView],
    rows: Mapping[uuid.UUID, Source],
    page: tuple[str | None, str],
) -> MonographDocument | None:
    chapter = field_chapter(row.field)
    drawn = drawn_delivery(delivered, place=(chapter, row.field), visible=visible, taken=())
    if drawn is None:
        return None
    sources = {str(key): stored_source(knowledge_view.source_ref(found)) for key, found in rows.items()}
    book = SourceBook()
    units, citations, claims = _cited(drawn.drafts, visible, book, sources)
    content = MonographContent(
        craft_slug=page[0] or SHARED_SUBJECT,
        sources=book.sources,
        citations=citations,
        citation_claims=claims,
        data={},
        units=units,
        components=[_entry(row, chapter)],
        layout=[
            LayoutEntry(chapter=chapter, kind="component", ref=row.label),
            *(LayoutEntry(chapter=chapter, kind="unit", ref=ref, within=row.label) for ref in drawn.drafts),
        ],
    )
    try:
        return MonographDocument(
            subject_kind="craft",
            subject_slug=page[0] or SHARED_SUBJECT,
            title=row.title,
            version=DOCUMENT_VERSION,
            content=content,
            specs={row.label: drawn.spec},
            page_url=page[1],
        )
    except ValidationError:
        return None


def _cited(
    drafts: Mapping[str, DraftUnit],
    visible: Mapping[uuid.UUID, ClaimView],
    book: SourceBook,
    sources: Mapping[str, CitedSource],
) -> tuple[dict[str, TextUnit], dict[str, Any], dict[str, list[str]]]:
    units: dict[str, TextUnit] = {}
    citations: dict[str, Any] = {}
    claims: dict[str, list[str]] = {}
    for ref, draft in drafts.items():
        unit, quotes = cited_unit(draft, visible, book, sources)
        units[ref] = unit
        if quotes:
            citations[ref] = quotes
            claims[ref] = list(unit.claim_ids)
    return units, citations, claims


def _entry(row: ComponentProposal, chapter: str) -> ComponentEntry:
    return ComponentEntry(
        label=row.label,
        chapter=chapter,
        anchor="#" + row.label.replace("/", "--"),
        kind=row.kind,
        title=row.title,
        description=row.description,
        field=row.field,
        fields=list(row.fields),
        subjects=[f"{SUBJECT_PREFIXES.get(s['kind'], 'craft')}:{s['key']}" for s in row.subjects],
    )


async def _facts(
    session: AsyncSession, claim_ids: Sequence[uuid.UUID], visible: Mapping[uuid.UUID, ClaimView]
) -> list[DeliveredFact]:
    if not claim_ids:
        return []
    rows = {claim.id: claim for claim in await session.scalars(select(Claim).where(Claim.id.in_(claim_ids)))}
    cited = await fact_sources(session, claim_ids)
    return [
        DeliveredFact(
            id=claim_id,
            text=rows[claim_id].text,
            level=rows[claim_id].evidenceLevel,
            shown=claim_id in visible,
            sources=cited.get(claim_id, []),
        )
        for claim_id in claim_ids
        if claim_id in rows
    ]
