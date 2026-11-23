import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.composer.region_story import StoryChoice, StoryStepChoice
from app.core.db import get_engine
from app.models import EnvDataset, KnowledgePiece as PieceRow, RiverBasin
from app.services import knowledge_view
from app.services.answer_events import cited_claims
from app.services.knowledge_view import resolve_craft
from app.services.piece_lookup import PieceAsk
from app.services.piece_store import BuiltSection
from app.services.place_offers import region_offer
from app.services.region_pieces import district_story_pieces, region_story_pieces
from app.services.region_story import region_story_block, story_statements

from ..geo.golden_region import KACHCHH
from ..migration_scripts import migration
from .test_knowledge_pieces_db import AJRAKH, QUESTION, WATER_CLAIMS, answer_row, prose_of, store_for
from .test_place_db import store_place

pytestmark = pytest.mark.db

NEIGHBOUR = 450


@pytest.fixture
async def session() -> AsyncIterator[AsyncSession]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            session = AsyncSession(bind=connection, expire_on_commit=False, autoflush=False)
            await session.execute(delete(RiverBasin))
            await session.execute(delete(EnvDataset))
            yield session
            await session.close()
        finally:
            await transaction.rollback()


async def told_without_a_river(session: AsyncSession) -> uuid.UUID:
    await store_place(session)
    offer = await region_offer(session, AJRAKH.slug)
    prose = await prose_of(session, WATER_CLAIMS)
    views, sources = await knowledge_view.claims_by_id(session, WATER_CLAIMS)
    statements = story_statements([prose], cited_claims(list(views.values()), sources))
    steps = [StoryStepChoice(claim=ref, district=f"d{KACHCHH}") for ref in statements]
    story = region_story_block(
        offer, statements, StoryChoice(river="none", steps=steps, layers=[]), block_id="s1.b2"
    )
    assert story is not None and story.river is None
    store = store_for(session)
    lookup = await store.reusable(PieceAsk(QUESTION, AJRAKH, ("GEOGRAPHY",), "EXPERT", fresh=True))
    answer_id = await answer_row(session)
    await store.keep(
        lookup, answer_id=answer_id, depth="EXPERT", sections=[BuiltSection("GEOGRAPHY", (prose, story))]
    )
    return answer_id


async def test_a_story_told_without_a_river_is_kept_with_its_districts_and_found_by_them(
    session: AsyncSession,
) -> None:
    answer_id = await told_without_a_river(session)
    rows = (await session.scalars(select(PieceRow).where(PieceRow.createdFromAnswerId == answer_id))).all()
    kept = {row.kind: (row.topicKey, row.districtLgds) for row in rows}
    assert kept["region_story"] == (f"water:lgd-{KACHCHH}", [KACHCHH])
    assert kept["prose"][1] == []
    craft = await resolve_craft(session, AJRAKH.slug)
    assert craft is not None
    found = await region_story_pieces(session, craft, ["GEOGRAPHY"])
    assert [piece.created_from_answer_id for piece in found] == [answer_id]
    assert [piece.created_from_answer_id for piece in await district_story_pieces(session, KACHCHH)] == [
        answer_id
    ]
    assert await district_story_pieces(session, NEIGHBOUR) == []


async def test_a_story_over_other_districts_is_not_found_for_the_craft(session: AsyncSession) -> None:
    answer_id = await told_without_a_river(session)
    await session.execute(
        text(
            'UPDATE "KnowledgePiece" SET "districtLgds" = :lgds WHERE "createdFromAnswerId" = :id AND kind = :kind'
        ),
        {"lgds": [KACHCHH, NEIGHBOUR], "id": answer_id, "kind": "region_story"},
    )
    craft = await resolve_craft(session, AJRAKH.slug)
    assert craft is not None
    assert await region_story_pieces(session, craft, ["GEOGRAPHY"]) == []
    assert [piece.created_from_answer_id for piece in await district_story_pieces(session, NEIGHBOUR)] == [
        answer_id
    ]


async def test_the_migration_fills_the_districts_of_stored_stories_told_without_a_river(
    session: AsyncSession,
) -> None:
    answer_id = await told_without_a_river(session)
    await session.execute(
        text(
            'UPDATE "KnowledgePiece" SET "districtLgds" = ARRAY[]::integer[] WHERE "createdFromAnswerId" = :id'
        ),
        {"id": answer_id},
    )
    await session.execute(text(migration("0083_piece_districts_and_places").TOLD_DISTRICTS))
    rows = (await session.scalars(select(PieceRow).where(PieceRow.createdFromAnswerId == answer_id))).all()
    assert {row.kind: row.districtLgds for row in rows} == {"region_story": [KACHCHH], "prose": []}
