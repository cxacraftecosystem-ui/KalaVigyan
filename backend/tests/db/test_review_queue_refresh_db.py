import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    ComponentProposal,
    Concept,
    Craft,
    CraftCategory,
    CraftSubCategory,
    ImageContribution,
    LayoutProposal,
    MediaAsset,
)
from app.research.page_revalidation import PageOwners
from app.research.review_queue import QueueDecision
from app.services import review_queue_refresh

from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 20, 9, tzinfo=UTC)
CATEGORY_SLUG = "refresh-test-category"
OWN_SLUG, FAMILY_SLUG, LINKED_SLUG, SHARED_SLUG = (
    "Refresh-Own-Craft",
    "Refresh-Family",
    "Refresh-Linked-Craft",
    "Refresh-Shared-Member",
)


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-review-queue-refresh/{name}")


CATEGORY, SUB, OTHER_SUB = key("category"), key("sub"), key("other-sub")
OWN, FAMILY, LINKED, SHARED = key("own"), key("family"), key("linked"), key("shared")
SHARED_CONCEPT, COMPONENT, LAYOUT, PICTURE = key("concept"), key("component"), key("layout"), key("picture")


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        opened.add(CraftCategory(id=CATEGORY, slug=CATEGORY_SLUG, name="Refresh", sortOrder=994))
        await opened.flush()
        opened.add_all(
            [
                CraftSubCategory(
                    id=SUB, slug="refresh-sub", name="Refresh", categoryId=CATEGORY, sortOrder=1
                ),
                CraftSubCategory(
                    id=OTHER_SUB, slug="refresh-other", name="Other", categoryId=CATEGORY, sortOrder=2
                ),
            ]
        )
        await opened.flush()
        opened.add_all(
            [
                Craft(id=OWN, slug=OWN_SLUG, name="Refresh Own", subCategoryId=SUB),
                Craft(id=FAMILY, slug=FAMILY_SLUG, name="Refresh Family", subCategoryId=SUB, isCatchAll=True),
                Craft(id=LINKED, slug=LINKED_SLUG, name="Refresh Linked"),
                Craft(id=SHARED, slug=SHARED_SLUG, name="Refresh Shared", subCategoryId=OTHER_SUB),
            ]
        )
        await opened.flush()
        opened.add(Concept(id=SHARED_CONCEPT, subCategoryId=OTHER_SUB, type="MATERIAL", name="Lime"))
        await opened.flush()
        await _decided_work(opened)
        yield opened


def _component() -> ComponentProposal:
    return ComponentProposal(
        id=COMPONENT,
        label="refresh-own-craft/chemistry/alum-table",
        title="Alum on cotton",
        description="A table of what alum does to the madder red on cotton, cited fact by fact.",
        kind="general_table",
        field="CHEMISTRY",
        craftId=OWN,
        subjects=[{"kind": "CRAFT", "key": LINKED_SLUG}, {"kind": "CONCEPT", "key": str(SHARED_CONCEPT)}],
        status="APPROVED",
        reviewedAt=NOW,
    )


async def _decided_work(session: AsyncSession) -> None:
    asset = MediaAsset(id=key("asset"), s3Key=f"media/refresh/{key('asset').hex}.png", mime="image/png")
    session.add(asset)
    await session.flush()
    session.add_all(
        [
            _component(),
            LayoutProposal(
                id=LAYOUT,
                subjectKind="category",
                categoryId=CATEGORY,
                baseVersion=0,
                entries=[],
                origin="AGENT",
                status="APPROVED",
                reviewedAt=NOW,
                layoutVersion=1,
            ),
            ImageContribution(
                id=PICTURE,
                craftId=LINKED,
                origin="PHOTOGRAPH",
                caption="The vat turns yellow-green",
                altText="A clay vat of yellow-green liquid",
                termsVersion="2026-11-19",
                rightsConfirmedAt=NOW,
                status="APPROVED",
                reviewedAt=NOW,
                assetId=asset.id,
            ),
        ]
    )
    await session.flush()


async def refreshed(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch, kind: str, item: uuid.UUID, status: str
) -> PageOwners:
    sent: list[PageOwners] = []

    async def refresh(owners: PageOwners) -> bool:
        sent.append(owners)
        return not owners.empty

    monkeypatch.setattr(review_queue_refresh, "refresh_pages", refresh)
    decided = QueueDecision(kind=kind, id=item, status=status, message="Decided.")
    await review_queue_refresh.refresh_after_decision(session, decided)
    (owners,) = sent
    return owners


async def test_an_approved_component_refreshes_its_craft_its_linked_crafts_and_its_concept_s_pages(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    owners = await refreshed(session, monkeypatch, "COMPONENTS", COMPONENT, "APPROVED")
    assert owners == PageOwners(
        crafts=(FAMILY_SLUG, LINKED_SLUG, OWN_SLUG, SHARED_SLUG), categories=(CATEGORY_SLUG,)
    )


async def test_an_approved_category_layout_refreshes_the_category_page_only(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    owners = await refreshed(session, monkeypatch, "LAYOUTS", LAYOUT, "APPROVED")
    assert owners == PageOwners(categories=(CATEGORY_SLUG,))


async def test_an_approved_picture_refreshes_its_craft_s_pages(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert await refreshed(session, monkeypatch, "IMAGES", PICTURE, "APPROVED") == PageOwners(
        crafts=(LINKED_SLUG,)
    )


@pytest.mark.parametrize(
    ("kind", "name"), [("COMPONENTS", "component"), ("LAYOUTS", "layout"), ("IMAGES", "picture")]
)
async def test_a_rejection_changes_no_page_so_it_refreshes_nothing(
    session: AsyncSession, monkeypatch: pytest.MonkeyPatch, kind: str, name: str
) -> None:
    assert await refreshed(session, monkeypatch, kind, key(name), "REJECTED") == PageOwners()
