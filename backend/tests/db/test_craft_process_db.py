import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.models import (
    Claim,
    Compound,
    ConditionReading,
    Craft,
    Material,
    Process,
    ProcessCondition,
    ProcessStage,
    Reaction,
    ReactionCitation,
    StageMaterial,
)
from app.research.retrieval import OPEN_CHUNK_ACLS
from app.schemas.science import CraftProcess
from app.science.process_view import craft_process
from app.services.craft_process import process_records
from app.services.science_seed import seed_science

from ..contracts.golden import dumped, golden_text
from ..science.golden_process import GOLDEN, LEFT_OUT_OF_THE_EXCERPT, claim_id, golden_rows

pytestmark = pytest.mark.db

INSERT_ORDER = (
    Process,
    ProcessStage,
    Compound,
    Material,
    StageMaterial,
    Reaction,
    ReactionCitation,
    ProcessCondition,
    ConditionReading,
)


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            session = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
            yield session
            await session.close()
        finally:
            await transaction.rollback()


async def craft(session: AsyncSession, slug: str) -> Craft:
    return (await session.execute(select(Craft).where(Craft.slug == slug))).scalar_one()


async def stored_process(session: AsyncSession, slug: str) -> CraftProcess:
    return craft_process(await process_records(session, await craft(session, slug)))


async def store_the_golden_excerpt(session: AsyncSession) -> None:
    ajrakh = await craft(session, "Kutch-Ajrakh")
    await session.execute(delete(Process).where(Process.craftId == ajrakh.id))
    hidden = [claim_id(key) for key in LEFT_OUT_OF_THE_EXCERPT]
    await session.execute(update(Claim).where(Claim.id.in_(hidden)).values(status="RETRACTED"))
    rows = golden_rows(ajrakh.id)
    for model in INSERT_ORDER:
        session.add_all([row for row in rows if isinstance(row, model)])
        await session.flush()


async def test_the_stored_rows_reproduce_the_golden_process(session: AsyncSession) -> None:
    await store_the_golden_excerpt(session)
    ajrakh = await craft(session, "Kutch-Ajrakh")
    process = craft_process(await process_records(session, ajrakh, acls=OPEN_CHUNK_ACLS))
    assert dumped(CraftProcess, process) == golden_text(GOLDEN)


async def test_the_seeded_ajrakh_process_carries_its_reactions_and_readings(session: AsyncSession) -> None:
    process = await stored_process(session, "Kutch-Ajrakh")
    stages = {stage.ordinal: stage for stage in process.processes[0].stages}
    assert sorted(stages) == list(range(1, 15))
    iron = stages[5].reactions[0]
    assert (iron.equation, iron.balanced, iron.checker_version) == (
        "Fe + 2 CH3COOH -> Fe(CH3COO)2 + H2",
        True,
        "balance/v1",
    )
    reduction, oxidation = stages[9].reactions
    assert reduction.equation == "C16H10N2O2 + 2 H^+ + 2 e^- -> C16H12N2O2"
    assert oxidation.equation == "2 C16H12N2O2 + O2 -> 2 C16H10N2O2 + 2 H2O"
    lake = stages[11].reactions[0]
    assert (lake.kind, lake.equation, lake.level_reason) == ("COMPLEXATION", None, None)
    [fermenting] = stages[5].conditions
    assert sorted((r.min, r.max) for r in fermenting.readings) == [(240.0, 360.0), (336.0, 336.0)]
    assert fermenting.sources_differ is False
    alum = next(m for m in stages[6].materials if m.name == "Alum (fatakdi)")
    assert (alum.kind, alum.role, alum.compound.formula) == ("MORDANT", "MORDANT", "KAl(SO4)2·12H2O")


async def test_two_sources_far_apart_on_the_bagh_bhatti_are_flagged(session: AsyncSession) -> None:
    process = await stored_process(session, "Bagh-Prints-Of-Madhya-Pradesh")
    bhatti = next(stage for stage in process.processes[0].stages if stage.ordinal == 8)
    [boiling] = bhatti.conditions
    assert sorted((r.min, r.max) for r in boiling.readings) == [(3.0, 3.0), (5.0, 6.0)]
    assert boiling.sources_differ is True


async def test_the_constants_are_stored_as_cited_claims(session: AsyncSession) -> None:
    ids = [
        uuid.UUID(str(claim_id(key)))
        for key in ("sci-constant-water-boiling-point", "sci-constant-quartz-inversion")
    ]
    found = (
        await session.execute(select(func.count()).select_from(Claim).where(Claim.id.in_(ids)))
    ).scalar_one()
    assert found == 2


async def test_seeding_the_science_again_changes_nothing(session: AsyncSession) -> None:
    before = (await session.execute(select(func.count()).select_from(ConditionReading))).scalar_one()
    result = await seed_science(session)
    after = (await session.execute(select(func.count()).select_from(ConditionReading))).scalar_one()
    assert before == after == result["total"]["readings"]
    assert result["skippedRows"] == 0
