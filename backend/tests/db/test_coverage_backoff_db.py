from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Claim, Concept, EnrichmentJob
from app.services.coverage_selection import least_covered_crafts, open_questions

from .write_back_seed import FAMILY, QUIET, key, seeded_session

pytestmark = pytest.mark.db


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async for opened in seeded_session():
        yield opened


async def chemistry_run(session: AsyncSession, started: datetime) -> None:
    session.add(
        EnrichmentJob(
            craftId=QUIET,
            status="SUCCEEDED",
            facets=["MATERIAL", "MECHANISM"],
            startedAt=started,
            finishedAt=started + timedelta(minutes=5),
            createdAt=started,
        )
    )
    binding = key("quiet-binding")
    session.add(Concept(id=binding, craftId=QUIET, type="MECHANISM", name="alum binding"))
    await session.flush()
    session.add(
        Claim(
            id=key("quiet-binds"),
            subjectType="CONCEPT",
            subjectId=binding,
            predicate="states",
            text="Alum binds the red to the cloth.",
            evidenceLevel="PROVISIONAL",
            origin="LIVE_RESEARCH",
            field="CHEMISTRY",
            createdAt=started + timedelta(minutes=1),
        )
    )
    await session.flush()


async def test_a_question_whose_last_run_added_nothing_to_its_field_rests_for_four_weeks(
    session: AsyncSession,
) -> None:
    now = datetime.now(UTC)
    await chemistry_run(session, now - timedelta(days=10))
    picked = await least_covered_crafts(session, now=now, limit=100_000)
    quiet = next(craft for craft in picked if craft.slug == "Zelvar-Quiet")
    assert (quiet.resting, dict(quiet.field_claims)) == (frozenset({"MATERIAL"}), {"CHEMISTRY": 1})
    assert [question.facet for question in open_questions(quiet)] == [
        "PROCESS_STAGE",
        "MECHANISM",
        "TOOL",
        "ENVIRONMENTAL_CONDITION",
        "HISTORICAL_CONTEXT",
    ]
    later = await least_covered_crafts(session, now=now + timedelta(days=19), limit=100_000)
    assert next(craft for craft in later if craft.slug == "Zelvar-Quiet").resting == frozenset()


async def shared_chemistry(session: AsyncSession, claims: int) -> None:
    shared = key("family-oxides")
    session.add(
        Concept(id=shared, craftId=None, subCategoryId=FAMILY, type="MECHANISM", name="family oxides")
    )
    await session.flush()
    for number in range(claims):
        session.add(
            Claim(
                id=key(f"family-oxide-{number}"),
                subjectType="CONCEPT",
                subjectId=shared,
                predicate="states",
                text=f"The family's glaze oxide {number} colours the surface.",
                evidenceLevel="PROVISIONAL",
                origin="LIVE_RESEARCH",
                field="CHEMISTRY",
            )
        )
    await session.flush()


@pytest.mark.parametrize(("claims", "counted", "asks_chemistry"), [(3, 1.5, True), (4, 2.0, False)])
async def test_the_family_s_shared_claims_count_at_half_weight_for_each_of_its_crafts(
    session: AsyncSession, claims: int, counted: float, asks_chemistry: bool
) -> None:
    await shared_chemistry(session, claims)
    picked = await least_covered_crafts(session, now=datetime.now(UTC), limit=100_000)
    quiet = next(craft for craft in picked if craft.slug == "Zelvar-Quiet")
    assert (quiet.claims, dict(quiet.field_claims)) == (counted, {"CHEMISTRY": counted})
    assert ("MECHANISM" in [question.facet for question in open_questions(quiet)]) is asks_chemistry
