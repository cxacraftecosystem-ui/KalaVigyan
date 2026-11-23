from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from functools import cache
from typing import Any

from app.curation.checks import default_context
from app.curation.files import CATEGORIES_DIR_NAME, CURATION_DIR, checked_dossier
from app.services.answer_events import cited_claims
from app.services.category_plan import CategoryPlan, CategoryTarget, category_plan
from app.services.curated_category_index import indexed_category_overview
from app.services.curation_overview import OverviewPieces, indexed_overview, overview_pieces
from app.services.curation_plan import CurationPlan
from app.services.curation_preview import plan_views
from app.services.dossier_export import git_dossier
from app.services.dossier_export_records import (
    CLAIM_COLUMNS,
    GI_COLUMNS,
    MARKER_COLUMNS,
    MEDIA_COLUMNS,
    PRICE_COLUMNS,
    QUOTE_COLUMNS,
    SOURCE_COLUMNS,
    STAGE_COLUMNS,
    USE_COLUMNS,
    WORKFORCE_COLUMNS,
    GitDossier,
    StoredCuration,
    StoredMarket,
    piece_sentences,
    projected,
)

from .category_support import registered
from .import_support import checked, plan_of

CRAFT_SCOPE = "CRAFT"
CATEGORY_SCOPE = "CATEGORY"


def stored_from_plan(plan: CurationPlan, *, scope: str = CRAFT_SCOPE) -> StoredCuration:
    districts = sorted(
        {place.district_lgd for place in plan.index.places if place.location_id and place.district_lgd}
    )
    overview = _overview(plan, plan.craft.id, districts)
    page = indexed_overview(plan.index, overview)
    rows = plan.rows
    gi = projected(rows["giRecords"], GI_COLUMNS)
    return StoredCuration(
        **_evidence(plan, overview),
        scope=scope,
        page=page,
        claim_order=tuple(page.claim_order),
        stages=_by_id(rows["stages"], STAGE_COLUMNS),
        uses=projected(rows["stageMaterials"], USE_COLUMNS),
        market=StoredMarket(
            gi=gi[0] if gi else None,
            prices=projected(rows["prices"], PRICE_COLUMNS),
            workforce=projected(rows["workforce"], WORKFORCE_COLUMNS),
        ),
    )


def stored_from_category_plan(plan: CategoryPlan) -> StoredCuration:
    overview = _overview(plan, None, [])
    return StoredCuration(
        **_evidence(plan, overview),
        scope=CATEGORY_SCOPE,
        page=indexed_category_overview(plan.index, overview),
    )


def _overview(
    plan: CurationPlan | CategoryPlan, craft_id: uuid.UUID | None, districts: list[int]
) -> OverviewPieces:
    views, sources = plan_views(plan)
    cited = cited_claims(list(views.values()), sources)
    return overview_pieces(plan.dossier, cited, craft_id=craft_id, districts=districts)


def _evidence(plan: CurationPlan | CategoryPlan, overview: OverviewPieces) -> dict[str, Any]:
    rows: Mapping[str, Sequence[Mapping[str, Any]]] = plan.rows
    return {
        "slug": plan.dossier.slug,
        "claims": _by_id(rows["claims"], CLAIM_COLUMNS),
        "markers": {row["claimId"]: row for row in projected(rows["curatedClaims"], MARKER_COLUMNS)},
        "quotes": projected(rows["claimSources"], QUOTE_COLUMNS),
        "sources": _by_id(rows["sources"], SOURCE_COLUMNS),
        "subjects": {row["id"]: row["originRef"] for row in rows["concepts"]},
        "media": _by_id(rows["media"], MEDIA_COLUMNS),
        "sentences": {piece.id: piece_sentences(piece.payload) for piece in overview.pieces},
    }


def _by_id(rows: Sequence[Mapping[str, Any]], columns: tuple[str, ...]) -> dict[uuid.UUID, dict[str, Any]]:
    return {row["id"]: row for row in projected(rows, columns)}


@cache
def stored_craft_of(slug: str) -> StoredCuration:
    result = checked(slug)
    assert result.dossier is not None
    return stored_from_plan(plan_of(slug), scope=result.dossier.scope)


@cache
def stored_category_of(slug: str) -> StoredCuration:
    result = checked_dossier(CURATION_DIR / CATEGORIES_DIR_NAME / f"{slug}.json", default_context())
    assert result.problems == () and result.dossier is not None and result.check is not None
    category = registered(slug)
    target = CategoryTarget(id=category.id, slug=category.slug, name=category.name)
    return stored_from_category_plan(category_plan(result.dossier, result.check, target))


def git_of(slug: str, *, category: bool = False) -> GitDossier:
    found = git_dossier(CURATION_DIR, slug, category=category)
    assert found is not None
    return found
