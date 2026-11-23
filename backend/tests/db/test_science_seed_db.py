import copy
import uuid
from collections.abc import AsyncIterator
from typing import Any

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.models import Compound, ConditionReading, Craft, Process, ProcessStage, Reaction, ReactionCitation
from app.services.claim_seed import seed_id
from app.services.science_seed import load_science_seed, seed_science

pytestmark = pytest.mark.db

ZINC_OXIDE = {"key": "zinc-oxide", "name": "Zinc oxide", "formula": "ZnO"}


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


def reaction_id(reaction: dict[str, Any]) -> uuid.UUID:
    return seed_id("reaction", f"{reaction['stage']}:{reaction['key']}")


def reading_id(condition: dict[str, Any], reading: dict[str, Any]) -> uuid.UUID:
    owner = f"{condition['stage']}:{condition['key']}"
    return seed_id("reading", f"{owner}:{reading['claim']}:{reading['citation']}")


async def another_writer_s_reaction(session: AsyncSession) -> uuid.UUID:
    craft_id = await session.scalar(select(Craft.id).order_by(Craft.slug).limit(1))
    process = Process(id=uuid.uuid4(), craftId=craft_id, name="Another writer's process")
    stage = ProcessStage(id=uuid.uuid4(), processId=process.id, ordinal=1, name="Another writer's stage")
    reaction = Reaction(id=uuid.uuid4(), stageId=stage.id, kind="OTHER", label="Another writer's reaction")
    session.add(process)
    await session.flush()
    session.add(stage)
    await session.flush()
    session.add(reaction)
    await session.flush()
    return reaction.id


async def citations_of(session: AsyncSession, reaction: uuid.UUID) -> int:
    counted = await session.scalar(
        select(func.count()).select_from(ReactionCitation).where(ReactionCitation.reactionId == reaction)
    )
    return int(counted or 0)


async def test_a_reaction_and_a_reading_taken_out_of_the_seed_are_deleted_and_other_rows_stay(
    session: AsyncSession,
) -> None:
    await seed_science(session)
    foreign = await another_writer_s_reaction(session)
    science = copy.deepcopy(load_science_seed())
    removed = science["reactions"].pop(0)
    condition = science["conditions"][0]
    dropped = condition["readings"].pop(1)
    assert await session.get(Reaction, reaction_id(removed)) is not None
    assert await citations_of(session, reaction_id(removed)) == len(removed["citations"])
    assert await session.get(ConditionReading, reading_id(condition, dropped)) is not None
    result = await seed_science(session, science)
    session.expunge_all()
    assert (result["deleted"]["reactions"], result["deleted"]["readings"]) == (1, 1)
    assert await session.get(Reaction, reaction_id(removed)) is None
    assert await citations_of(session, reaction_id(removed)) == 0
    assert await session.get(ConditionReading, reading_id(condition, dropped)) is None
    assert await session.get(ConditionReading, reading_id(condition, condition["readings"][0])) is not None
    assert await session.get(Reaction, foreign) is not None


async def test_a_compound_taken_out_of_the_seed_that_nothing_names_is_deleted(session: AsyncSession) -> None:
    science = copy.deepcopy(load_science_seed())
    science["compounds"].append(dict(ZINC_OXIDE))
    await seed_science(session, science)
    zinc = seed_id("compound", "zinc-oxide")
    assert await session.get(Compound, zinc) is not None
    science["compounds"].pop()
    result = await seed_science(session, science)
    session.expunge_all()
    assert result["deleted"]["compounds"] == 1
    assert await session.get(Compound, zinc) is None
    assert await session.get(Compound, seed_id("compound", "alizarin")) is not None


async def test_seeding_the_whole_seed_again_deletes_nothing(session: AsyncSession) -> None:
    await seed_science(session)
    result = await seed_science(session)
    assert all(count == 0 for count in result["deleted"].values())
