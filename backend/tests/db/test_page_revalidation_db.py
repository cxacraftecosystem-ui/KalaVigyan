import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Claim, Concept, Craft, CraftCategory, CraftSubCategory, CuratedCategoryClaim
from app.research.page_revalidation import PageOwners
from app.services.page_revalidation import claim_owners, craft_owners

from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

CATEGORY_SLUG = "revalidation-test-category"
CRAFT_SLUG, FAMILY_SLUG, ALL_INDIA_SLUG = (
    "Revalidation-Craft",
    "Revalidation-Family",
    "Revalidation-All-India",
)


def key(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_URL, f"test-page-revalidation/{name}")


CATEGORY, SUB_CATEGORY, CRAFT, FAMILY, ALL_INDIA = (
    key("category"),
    key("sub-category"),
    key("craft"),
    key("family"),
    key("all-india"),
)
OWN_CONCEPT, SHARED_CONCEPT = key("own-concept"), key("shared-concept")
OWN_CLAIM, SHARED_CLAIM, CATEGORY_CLAIM = key("own-claim"), key("shared-claim"), key("category-claim")


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        for rows in _rows():
            opened.add_all(rows)
            await opened.flush()
        yield opened


def _rows() -> list[list[object]]:
    sub_category = CraftSubCategory(
        id=SUB_CATEGORY, slug="revalidation-sub", name="Revalidation", categoryId=CATEGORY, sortOrder=1
    )
    return [
        [CraftCategory(id=CATEGORY, slug=CATEGORY_SLUG, name="Revalidation", sortOrder=995)],
        [sub_category],
        _crafts(),
        [
            Concept(id=OWN_CONCEPT, craftId=CRAFT, type="MATERIAL", name="Alum"),
            Concept(id=SHARED_CONCEPT, subCategoryId=SUB_CATEGORY, type="MATERIAL", name="Lime"),
        ],
        [
            _claim(OWN_CLAIM, OWN_CONCEPT),
            _claim(SHARED_CLAIM, SHARED_CONCEPT),
            _claim(CATEGORY_CLAIM, SHARED_CONCEPT),
        ],
        [
            CuratedCategoryClaim(
                claimId=CATEGORY_CLAIM, categoryId=CATEGORY, key="C001", discipline="MATERIALS"
            )
        ],
    ]


def _crafts() -> list[object]:
    return [
        Craft(id=CRAFT, slug=CRAFT_SLUG, name="Revalidation Craft", subCategoryId=SUB_CATEGORY),
        Craft(
            id=FAMILY,
            slug=FAMILY_SLUG,
            name="Revalidation Family",
            subCategoryId=SUB_CATEGORY,
            isCatchAll=True,
        ),
        Craft(
            id=ALL_INDIA,
            slug=ALL_INDIA_SLUG,
            name="Revalidation All India",
            subCategoryId=SUB_CATEGORY,
            stateOfPractice=["All India"],
        ),
    ]


def _claim(claim_id: uuid.UUID, concept_id: uuid.UUID) -> Claim:
    return Claim(
        id=claim_id,
        subjectType="CONCEPT",
        subjectId=concept_id,
        predicate="states",
        text="Alum fixes the red dye to the cotton cloth.",
        evidenceLevel="PROVISIONAL",
        origin="IMPORT",
        field="MATERIALS",
    )


async def test_a_craft_s_pages_are_its_own_its_families_and_its_category(session: AsyncSession) -> None:
    assert await craft_owners(session, [CRAFT]) == PageOwners(
        crafts=(ALL_INDIA_SLUG, CRAFT_SLUG, FAMILY_SLUG), categories=(CATEGORY_SLUG,)
    )
    assert await craft_owners(session, []) == PageOwners()


async def test_a_fact_reaches_the_pages_of_the_concept_it_is_about(session: AsyncSession) -> None:
    own = await claim_owners(session, [OWN_CLAIM])
    assert own == PageOwners(crafts=(ALL_INDIA_SLUG, CRAFT_SLUG, FAMILY_SLUG), categories=(CATEGORY_SLUG,))
    shared = await claim_owners(session, [SHARED_CLAIM])
    assert shared == PageOwners(crafts=(ALL_INDIA_SLUG, FAMILY_SLUG), categories=(CATEGORY_SLUG,))
    curated = await claim_owners(session, [CATEGORY_CLAIM])
    assert curated == PageOwners(crafts=(ALL_INDIA_SLUG, FAMILY_SLUG), categories=(CATEGORY_SLUG,))
