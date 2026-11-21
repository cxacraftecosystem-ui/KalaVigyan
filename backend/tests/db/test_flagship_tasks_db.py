import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import (
    Claim,
    ComponentProposal,
    Concept,
    CraftCategory,
    CuratedCategoryClaim,
    KnowledgePiece,
    PageLayout,
    User,
)
from app.research.open_work import TaskKey, Viewer, WorkFilters
from app.services.open_work import list_open_work, open_task
from app.services.task_reservations import claim_task

from .testimony_seed import rolled_back_session

pytestmark = pytest.mark.db

NOW = datetime(2026, 11, 21, 12, 0, tzinfo=UTC)
SITE = "https://kalavigyan.example"
METAL = "Metal-Craft-Category"
KEY = TaskKey("FLAGSHIP", "category", METAL)
WAX = uuid.UUID("f1a90000-0000-4000-8000-000000000001")
WAX_FACT = uuid.UUID("f1a90000-0000-4000-8000-000000000002")
RESEARCHER = uuid.UUID("f1a90000-0000-4000-8000-000000000003")
FIRST_FACT = uuid.UUID("b6ecc15b-7df9-5345-910e-3567fcde20d1")


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in rolled_back_session():
        yield opened


async def family_page(session: AsyncSession) -> uuid.UUID:
    found = await session.scalar(select(CraftCategory.id).where(CraftCategory.slug == METAL))
    if found is not None:
        return found
    category = CraftCategory(id=uuid.uuid4(), slug=METAL, name="Flagship Test Metal", sortOrder=994)
    session.add(category)
    await session.flush()
    return category.id


async def wax_fact(session: AsyncSession) -> None:
    session.add(Concept(id=WAX, type="MATERIAL", name="Flagship test beeswax"))
    await session.flush()
    session.add(
        Claim(
            id=WAX_FACT,
            subjectType="CONCEPT",
            subjectId=WAX,
            predicate="states",
            text="The wax model is coated in clay before the metal replaces it.",
            evidenceLevel="PROVISIONAL",
            origin="IMPORT",
            field="PROCESS",
        )
    )
    await session.flush()


async def page_fact(session: AsyncSession, category_id: uuid.UUID) -> None:
    await wax_fact(session)
    session.add(
        CuratedCategoryClaim(claimId=WAX_FACT, categoryId=category_id, key="F9001", discipline="PROCESS")
    )
    await session.flush()


def piece(kind: str, label: str, claims: list[uuid.UUID]) -> KnowledgePiece:
    return KnowledgePiece(
        craftId=None,
        kind=kind,
        facet="PROCESS",
        topicKey=f"component:{label}",
        language="en",
        depth="EXPERT",
        payload={},
        claimIds=claims,
        sourceIds=["flagship-test-source"],
        contentHash=uuid.uuid4().hex + uuid.uuid4().hex,
        label=label,
        title="Flagship test figure",
        description="A figure drawn for the flagship tests from the family page's own facts.",
        fields=[],
    )


async def flagship_keys(session: AsyncSession) -> list[str]:
    work = await list_open_work(
        session, WorkFilters(category_slug=METAL, kind="FLAGSHIP"), Viewer(), site=SITE, now=NOW
    )
    return [task.key for task in work.tasks]


async def test_a_family_page_without_its_player_holds_one_flagship_task_from_the_backlog(
    session: AsyncSession,
) -> None:
    await family_page(session)
    task = await open_task(session, KEY, site=SITE)
    assert task is not None
    assert (task.key, task.kind, task.priority, task.prompt) == (
        "FLAGSHIP:category:Metal-Craft-Category",
        "FLAGSHIP",
        "HIGH",
        "deliver_page",
    )
    assert task.subject is not None and (task.subject.kind, task.subject.slug) == ("category", METAL)
    assert task.fact_ids[0] == FIRST_FACT and task.count == len(task.fact_ids) == 17
    assert await flagship_keys(session) == ["FLAGSHIP:category:Metal-Craft-Category"]


async def test_a_player_resting_on_the_family_page_s_facts_closes_it(session: AsyncSession) -> None:
    await page_fact(session, await family_page(session))
    session.add(piece("chart", "shared/process/flagship-test-casting-chart", [WAX_FACT]))
    await session.flush()
    assert await open_task(session, KEY, site=SITE) is not None
    session.add(piece("reaction_player", "shared/process/flagship-test-lost-wax", [WAX_FACT]))
    await session.flush()
    assert await open_task(session, KEY, site=SITE) is None
    assert await flagship_keys(session) == []


async def test_a_player_named_in_the_family_page_s_layout_closes_it(session: AsyncSession) -> None:
    category_id = await family_page(session)
    await wax_fact(session)
    label = "shared/process/flagship-test-dip"
    session.add(piece("dip_player", label, [WAX_FACT]))
    await session.flush()
    assert await open_task(session, KEY, site=SITE) is not None
    latest = await session.scalar(
        select(func.max(PageLayout.version)).where(PageLayout.categoryId == category_id)
    )
    entry = {"ref": label, "chapter": "why", "order": 1, "role": "FIGURE"}
    session.add(PageLayout(categoryId=category_id, version=(latest or 0) + 1, entries=[entry]))
    await session.flush()
    assert await open_task(session, KEY, site=SITE) is None


async def test_a_waiting_proposal_naming_the_task_closes_it_and_a_contributor_can_claim_it(
    session: AsyncSession,
) -> None:
    await family_page(session)
    session.add(
        User(id=RESEARCHER, name="Flagship Researcher", email="flagship@example.org", role="RESEARCHER")
    )
    await session.flush()
    held = await claim_task(session, RESEARCHER, "FLAGSHIP:category:Metal-Craft-Category", site=SITE, now=NOW)
    assert held.held is True and held.task is not None and held.task.kind == "FLAGSHIP"
    session.add(
        ComponentProposal(
            proposerId=RESEARCHER,
            label="shared/process/flagship-test-proposed-player",
            title="Lost-wax casting, state by state",
            description="A player stepping a dhokra figure through its core, wax, coat, fire, pour and break.",
            kind="reaction_player",
            field="PROCESS",
            subjects=[{"kind": "CRAFT", "key": "Bastar-Dhokra"}],
            taskKey="FLAGSHIP:category:Metal-Craft-Category",
        )
    )
    await session.flush()
    assert await flagship_keys(session) == []
