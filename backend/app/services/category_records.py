from __future__ import annotations

import uuid
from collections.abc import Collection, Iterable, Mapping, Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Claim, CuratedCategory, CuratedCategoryClaim
from app.research.citations import SourceRef
from app.research.knowledge_pieces import KnowledgePiece
from app.research.media_refs import MediaRef

from . import knowledge_view
from .category_page import CategoryClaimFacts, CategoryPageRecords
from .category_register import CategoryRecord, stored_categories
from .claim_holds import unheld_by_id
from .curated_category_index import CuratedCategoryPage, stored_category_page
from .media_ref_store import stored_media_refs
from .piece_lookup import stored_pieces

__all__ = ["category_list_records", "category_page_records"]


@dataclass(frozen=True)
class _Wanted:
    category: CategoryRecord
    curated: CuratedCategoryPage
    claim_ids: tuple[uuid.UUID, ...]
    pieces: Mapping[uuid.UUID, KnowledgePiece]


@dataclass(frozen=True)
class _Fetched:
    views: Mapping[uuid.UUID, knowledge_view.ClaimView]
    facts: Mapping[uuid.UUID, CategoryClaimFacts]
    sources: Mapping[str, SourceRef]
    media: Mapping[uuid.UUID, MediaRef]


async def category_page_records(session: AsyncSession, slug: str) -> CategoryPageRecords | None:
    found = await stored_categories(session, slug=slug)
    if not found:
        return None
    category = found[0]
    curated = (await _curated_pages(session, [category.id])).get(category.id)
    if curated is None:
        return CategoryPageRecords(category=category)
    marked = select(CuratedCategoryClaim.claimId).where(CuratedCategoryClaim.categoryId == category.id)
    claim_ids = tuple(await session.scalars(marked))
    pieces = await stored_pieces(session, list(curated.piece_ids().values()))
    [records] = await _records(session, [_Wanted(category, curated, claim_ids, pieces)])
    return records


async def category_list_records(session: AsyncSession) -> list[CategoryPageRecords]:
    categories = await stored_categories(session)
    pages = await _curated_pages(session, [category.id for category in categories])
    ledes = await stored_pieces(
        session, [page.overview.lede_piece_id for page in pages.values() if page.overview.lede_piece_id]
    )
    wanted = [_listed(category, pages[category.id], ledes) for category in categories if category.id in pages]
    built = {records.category.id: records for records in await _records(session, wanted)}
    return [
        built[category.id] if category.id in built else CategoryPageRecords(category=category)
        for category in categories
    ]


def _listed(
    category: CategoryRecord, curated: CuratedCategoryPage, ledes: Mapping[uuid.UUID, KnowledgePiece]
) -> _Wanted:
    lede = ledes.get(curated.overview.lede_piece_id) if curated.overview.lede_piece_id else None
    pictured = (claim_id for picture in curated.pictures for claim_id in picture.claim_ids)
    claim_ids = (*(lede.claim_ids if lede else ()), *pictured)
    return _Wanted(category, curated, claim_ids, {lede.id: lede} if lede else {})


async def _records(session: AsyncSession, wanted: Sequence[_Wanted]) -> list[CategoryPageRecords]:
    fetched = await _fetched(session, wanted)
    return [_sliced(one, fetched) for one in wanted]


async def _fetched(session: AsyncSession, wanted: Sequence[_Wanted]) -> _Fetched:
    views, sources = await knowledge_view.claims_by_id(session, (c for one in wanted for c in one.claim_ids))
    views = await unheld_by_id(session, views)
    media_ids = [picture.media_ref_id for one in wanted for picture in one.curated.pictures]
    return _Fetched(
        views=views,
        facts=await _facts(session, views.keys()),
        sources={
            str(key): SourceRef.model_validate(knowledge_view.source_ref(row)) for key, row in sources.items()
        },
        media=await stored_media_refs(session, list(dict.fromkeys(media_ids))),
    )


def _sliced(wanted: _Wanted, fetched: _Fetched) -> CategoryPageRecords:
    views = [fetched.views[c] for c in dict.fromkeys(wanted.claim_ids) if c in fetched.views]
    cited = {citation["sourceId"] for view in views for citation in view.citations}
    pictured = [picture.media_ref_id for picture in wanted.curated.pictures]
    return CategoryPageRecords(
        category=wanted.category,
        curated=wanted.curated,
        views=tuple(views),
        facts={view.id: fetched.facts[view.id] for view in views if view.id in fetched.facts},
        sources={key: ref for key, ref in fetched.sources.items() if key in cited},
        pieces=wanted.pieces,
        media={ref_id: fetched.media[ref_id] for ref_id in pictured if ref_id in fetched.media},
    )


async def _curated_pages(
    session: AsyncSession, category_ids: Collection[uuid.UUID]
) -> dict[uuid.UUID, CuratedCategoryPage]:
    if not category_ids:
        return {}
    rows = await session.execute(
        select(CuratedCategory.categoryId, CuratedCategory.page).where(
            CuratedCategory.categoryId.in_(list(category_ids))
        )
    )
    pages = {category_id: stored_category_page(category_id, page) for category_id, page in rows.tuples()}
    return {category_id: page for category_id, page in pages.items() if page is not None}


async def _facts(
    session: AsyncSession, claim_ids: Iterable[uuid.UUID]
) -> dict[uuid.UUID, CategoryClaimFacts]:
    wanted = list(claim_ids)
    if not wanted:
        return {}
    rows = await session.execute(
        select(Claim.id, CuratedCategoryClaim.discipline, Claim.sourcesDiffer)
        .join(CuratedCategoryClaim, CuratedCategoryClaim.claimId == Claim.id)
        .where(Claim.id.in_(wanted))
    )
    return {
        claim_id: CategoryClaimFacts(discipline, differ) for claim_id, discipline, differ in rows.tuples()
    }
