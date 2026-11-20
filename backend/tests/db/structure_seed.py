import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.data.craft_master_loader import ID_NAMESPACE
from app.models import (
    Claim,
    Concept,
    Craft,
    CraftCategory,
    CraftSubCategory,
    CuratedClaim,
    CuratedCraft,
    User,
)
from app.research.fetcher import FetchedPage, PageMetadata
from app.research.structure_proposals import StructureProposal, StructureProposalResult
from app.services.curated_index import CuratedPage
from app.services.structure_proposals import propose_structure

from ..knowledge_writes.fakes import FakeFetcher
from ..structure.pages import (
    HELD_A,
    HELD_B,
    HELD_C,
    HISTORY_CONCEPT,
    MATERIAL_CONCEPT,
    OTHER_CONCEPT,
    PAGE_TEXT,
    PAGE_URL,
    SLUG,
    STAGE_CONCEPT,
    curated_page,
    key,
    proposal,
)
from .testimony_seed import rolled_back_session

__all__ = [
    "CRAFT",
    "NOW",
    "SITE",
    "People",
    "curated_key",
    "fetched",
    "proposed",
    "seeded_session",
    "stored_page",
    "with_page",
]

NOW = datetime(2026, 11, 20, 10, tzinfo=UTC)
SITE = "https://kalavigyan.example"
CRAFT, CATEGORY, SUB_CATEGORY = key("craft"), key("category"), key("sub-category")
RESEARCHER, PROFESSOR = key("researcher"), key("professor")
HELD_TEXTS = {
    HELD_A: "The cloth is washed in the river twice before it is printed.",
    HELD_B: "The river near the dye houses dried in 2001.",
    HELD_C: "The river near the dye houses still ran in 2003.",
}


@dataclass(frozen=True)
class People:
    researcher: User
    professor: User


def curated_key(claim_key: str) -> uuid.UUID:
    return uuid.uuid5(ID_NAMESPACE, f"curation:{SLUG}:{claim_key}")


def fetched(text: str = PAGE_TEXT) -> FetchedPage:
    return FetchedPage(
        url=PAGE_URL,
        final_url=PAGE_URL,
        status=200,
        content_type="text/html",
        bytes=len(text),
        sha256="0" * 64,
        fetched_at=NOW,
        text=text,
        truncated=False,
        metadata=PageMetadata(title="Dyeing in the delta"),
    )


async def proposed(
    session: AsyncSession, user: User, item: dict[str, Any], *, text: str = PAGE_TEXT, **changes: Any
) -> StructureProposalResult:
    body: StructureProposal = proposal(item, **changes)
    fetcher = FakeFetcher({PAGE_URL: fetched(text)})
    return await propose_structure(session, user, body, context=("CONTRIBUTION", fetcher, SITE), now=NOW)


async def stored_page(session: AsyncSession) -> CuratedPage:
    page = await session.get(CuratedCraft, CRAFT, populate_existing=True)
    assert page is not None
    return CuratedPage.model_validate(page.page)


async def with_page(session: AsyncSession, page: CuratedPage) -> None:
    await session.execute(
        update(CuratedCraft)
        .where(CuratedCraft.craftId == CRAFT)
        .values(page=page.model_dump(mode="json", by_alias=True))
    )


async def seeded_session() -> AsyncIterator[tuple[AsyncSession, People]]:
    async for opened in rolled_back_session():
        people = People(_person(RESEARCHER, "RESEARCHER"), _person(PROFESSOR, "PROFESSOR"))
        opened.add_all([people.researcher, people.professor])
        opened.add(
            CraftCategory(id=CATEGORY, slug="structure-test-category", name="Structure", sortOrder=996)
        )
        await opened.flush()
        opened.add(
            CraftSubCategory(
                id=SUB_CATEGORY,
                slug="structure-test-family",
                name="Structure",
                categoryId=CATEGORY,
                sortOrder=1,
            )
        )
        await opened.flush()
        opened.add(Craft(id=CRAFT, slug=SLUG, name="Structure Test Craft", subCategoryId=SUB_CATEGORY))
        await opened.flush()
        opened.add_all(_concepts())
        await opened.flush()
        opened.add_all([_held(claim_id, text) for claim_id, text in HELD_TEXTS.items()])
        await opened.flush()
        opened.add_all(_markers())
        opened.add(_curated(curated_page()))
        await opened.flush()
        yield opened, people


def _person(user_id: uuid.UUID, role: str) -> User:
    return User(id=user_id, name=f"{role.title()} Tester", email=f"{user_id.hex[:12]}@example.org", role=role)


def _concepts() -> list[Concept]:
    named = (
        (STAGE_CONCEPT, "PROCESS_STAGE", "Second wash", "P01"),
        (OTHER_CONCEPT, "PROCESS_STAGE", "Printing", "P02"),
        (MATERIAL_CONCEPT, "MATERIAL", "Indigo", "M01"),
        (HISTORY_CONCEPT, "HISTORICAL_CONTEXT", "Structure Test Craft", "craft:HISTORY"),
    )
    return [
        Concept(id=concept_id, craftId=CRAFT, type=kind, name=name, originRef=f"curation:{SLUG}:{origin}")
        for concept_id, kind, name, origin in named
    ]


def _held(claim_id: uuid.UUID, text: str) -> Claim:
    return Claim(
        id=claim_id,
        subjectType="CONCEPT",
        subjectId=HISTORY_CONCEPT,
        predicate="states",
        text=text,
        evidenceLevel="PROVISIONAL",
        origin="IMPORT",
        status="APPROVED",
        field="HISTORY",
    )


def _markers() -> list[CuratedClaim]:
    keys = {HELD_A: "C001", HELD_B: "C002", HELD_C: "C003"}
    return [
        CuratedClaim(claimId=claim_id, craftId=CRAFT, key=claim_key, discipline="HISTORY")
        for claim_id, claim_key in keys.items()
    ]


def _curated(page: CuratedPage) -> CuratedCraft:
    return CuratedCraft(
        craftId=CRAFT,
        version=page.version,
        curatedAt=page.curated_at,
        coverage=page.coverage,
        digest="0" * 64,
        page=page.model_dump(mode="json", by_alias=True),
    )
