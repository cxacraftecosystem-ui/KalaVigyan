from __future__ import annotations

import uuid
from collections import Counter
from collections.abc import Iterable, Mapping
from typing import Any

import pytest

from app.curation.dossier import Dossier
from app.research.category_page import CategoryPage
from app.services import category_records
from app.services.category_page import CategoryPageRecords, category_list, category_page
from app.services.category_plan import CategoryTarget, category_plan
from app.services.category_preview import preview_category_records
from app.services.category_register import register_categories
from app.services.curation_preview import plan_views

from ..contracts.golden import golden_json
from .category_support import LEATHER, PAGE_GOLDEN, PAPER, leather_checked, leather_plain, recheck, registered

CURATED = (LEATHER, PAPER)
ONE_READ_EACH = {"categories": 1, "pages": 1, "pieces": 1, "claims": 1, "holds": 1, "facts": 1, "media": 1}


def curated_as(slug: str) -> tuple[CategoryPageRecords, Mapping[uuid.UUID, Any], Mapping[uuid.UUID, Any]]:
    plain = leather_plain()
    plain["categorySlug"] = slug
    dossier = Dossier.model_validate(plain)
    check = recheck(leather_checked()[1], dossier)
    category = registered(slug)
    plan = category_plan(
        dossier, check, CategoryTarget(id=category.id, slug=category.slug, name=category.name)
    )
    views, sources = plan_views(plan)
    return preview_category_records(dossier, check, category), views, sources


class MarkedClaims:
    def __init__(self, claim_ids: Iterable[uuid.UUID]) -> None:
        self.claim_ids = tuple(claim_ids)

    async def scalars(self, _statement: Any) -> Iterable[uuid.UUID]:
        return iter(self.claim_ids)


@pytest.fixture(scope="module")
def stored() -> dict[str, tuple[CategoryPageRecords, Mapping[uuid.UUID, Any], Mapping[uuid.UUID, Any]]]:
    return {slug: curated_as(slug) for slug in CURATED}


@pytest.fixture
def reads(monkeypatch: pytest.MonkeyPatch, stored: dict[str, Any]) -> Counter[str]:
    records = {found.category.id: found for found, _, _ in stored.values()}
    views = {key: view for _, found, _ in stored.values() for key, view in found.items()}
    sources = {key: row for _, _, found in stored.values() for key, row in found.items()}
    counted: Counter[str] = Counter()

    def lookup(name: str, table: Mapping[uuid.UUID, Any]) -> Any:
        async def fetch(_session: Any, keys: Iterable[uuid.UUID]) -> dict[uuid.UUID, Any]:
            counted[name] += 1
            return {key: table[key] for key in keys if key in table}

        return fetch

    async def categories(_session: Any, *, slug: str | None = None) -> tuple[Any, ...]:
        counted["categories"] += 1
        return tuple(category for category in register_categories() if slug in (None, category.slug))

    async def claims(
        _session: Any, claim_ids: Iterable[uuid.UUID]
    ) -> tuple[dict[uuid.UUID, Any], dict[Any, Any]]:
        counted["claims"] += 1
        found = {key: views[key] for key in claim_ids if key in views}
        cited = {uuid.UUID(c["sourceId"]) for view in found.values() for c in view.citations}
        return found, {key: sources[key] for key in cited}

    async def unheld(_session: Any, found: Mapping[uuid.UUID, Any]) -> dict[uuid.UUID, Any]:
        counted["holds"] += 1
        return dict(found)

    monkeypatch.setattr(category_records, "stored_categories", categories)
    monkeypatch.setattr(category_records, "unheld_by_id", unheld)
    monkeypatch.setattr(category_records.knowledge_view, "claims_by_id", claims)
    monkeypatch.setattr(
        category_records, "_curated_pages", lookup("pages", {k: r.curated for k, r in records.items()})
    )
    monkeypatch.setattr(category_records, "stored_pieces", lookup("pieces", merged(records, "pieces")))
    monkeypatch.setattr(category_records, "_facts", lookup("facts", merged(records, "facts")))
    monkeypatch.setattr(category_records, "stored_media_refs", lookup("media", merged(records, "media")))
    return counted


def merged(records: Mapping[uuid.UUID, CategoryPageRecords], part: str) -> dict[uuid.UUID, Any]:
    return {key: value for found in records.values() for key, value in getattr(found, part).items()}


async def test_the_list_reads_each_kind_of_record_once_however_many_categories_are_curated(
    reads: Counter[str],
) -> None:
    listed = await category_records.category_list_records(None)
    assert sum(1 for records in listed if records.curated is not None) == len(CURATED)
    assert reads == ONE_READ_EACH


async def test_each_listed_category_keeps_only_its_own_claims_sources_and_pictures(
    reads: Counter[str], stored: dict[str, Any]
) -> None:
    listed = {
        records.category.slug: records for records in await category_records.category_list_records(None)
    }
    for slug in CURATED:
        own = stored[slug][0]
        served = listed[slug]
        assert served.views and {view.id for view in served.views} <= {view.id for view in own.views}
        assert served.sources and set(served.sources) <= set(own.sources)
        assert set(served.facts) == {view.id for view in served.views}
        assert served.media == own.media
    whole = [
        stored[c.slug][0] if c.slug in stored else CategoryPageRecords(category=c)
        for c in register_categories()
    ]
    assert category_list(list(listed.values())) == category_list(whole)


async def test_a_category_page_reads_each_kind_of_record_once(
    reads: Counter[str], stored: dict[str, Any]
) -> None:
    records = await category_records.category_page_records(MarkedClaims(stored[LEATHER][0].facts), LEATHER)
    assert records is not None
    assert category_page(records) == CategoryPage.model_validate(golden_json(PAGE_GOLDEN))
    assert reads == ONE_READ_EACH
