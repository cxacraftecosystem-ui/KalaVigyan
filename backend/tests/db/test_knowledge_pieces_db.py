import hashlib
import json
import uuid
from collections.abc import AsyncIterator, Sequence
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete, exists, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_engine
from app.core.errors import ExternalFailure
from app.core.shielded import ShieldedWork
from app.models import (
    Answer,
    Claim,
    ClaimSource,
    Concept,
    Craft,
    CuratedClaim,
    KnowledgePiece as PieceRow,
    Process,
    ProcessStage,
    Source,
    User,
)
from app.research.blocks import ExplainerSentence, ProseBlock
from app.research.citations import Citation
from app.research.crafts import CraftRef
from app.research.embedding import TextEmbedder
from app.research.knowledge_pieces import PieceSlot, knowledge_piece
from app.research.retrieval import OPEN_CHUNK_ACLS
from app.retrieval.indexing import embed_pieces
from app.science.ladder import process_ladder
from app.services import knowledge_view
from app.services.craft_process import process_records
from app.services.piece_lookup import PieceAsk, PieceLookup
from app.services.piece_rebuild import StaleGroup, mark_rebuild_tried, stale_groups
from app.services.piece_store import BuiltSection, SqlPieceStore, piece_values

pytestmark = pytest.mark.db

AJRAKH = CraftRef(slug="Kutch-Ajrakh", name="Kutch Ajrakh", path="/crafts/Kutch-Ajrakh")
WATER_CLAIMS = (
    uuid.UUID("6d42a538-0a5e-5cfb-b8f5-68012eb0d4d6"),
    uuid.UUID("826c1d72-9373-59f0-85c3-6bb38aa89320"),
    uuid.UUID("faa466c1-8940-5552-a7f5-851cebb40f64"),
)
QUESTION = "Why does the water of Kutch matter for Ajrakh?"
DIMENSIONS = 1536


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


async def fixed_embedder(texts: list[str]) -> list[list[float]]:
    return [[1.0] + [0.0] * (DIMENSIONS - 1) for _ in texts]


async def failing_embedder(texts: list[str]) -> list[list[float]]:
    raise ExternalFailure("embeddings are down", kind="unavailable", service="embeddings")


def store_for(session: AsyncSession, embed: TextEmbedder = fixed_embedder) -> SqlPieceStore:
    def sessions() -> AsyncSession:
        return AsyncSession(bind=session.bind, expire_on_commit=False, autoflush=False)

    return SqlPieceStore(sessions, embed=embed, shield=ShieldedWork())


async def prose_of(
    session: AsyncSession, claim_ids: Sequence[uuid.UUID], *, acls: Sequence[str] = OPEN_CHUNK_ACLS
) -> ProseBlock:
    views, _ = await knowledge_view.claims_by_id(session, claim_ids, acls=acls)
    sentences = [
        ExplainerSentence(
            id=f"s1.b1.{n}",
            text=views[claim_id].text,
            level=views[claim_id].level,
            citations=[Citation.model_validate(c) for c in views[claim_id].citations],
            terms=[],
        )
        for n, claim_id in enumerate(claim_ids, start=1)
    ]
    return ProseBlock(id="s1.b1", kind="prose", version=1, reuse=None, sentences=sentences)


async def answer_row(session: AsyncSession, *, user_id: uuid.UUID | None = None) -> uuid.UUID:
    craft = await knowledge_view.resolve_craft(session, AJRAKH.slug)
    answer_id = uuid.uuid4()
    session.add(Answer(id=answer_id, userId=user_id, question=QUESTION, mode="DEEP", craftId=craft.id))
    await session.flush()
    return answer_id


async def kept(
    session: AsyncSession,
    store: SqlPieceStore,
    *,
    depth: str = "EXPERT",
    claims: Sequence[uuid.UUID] = WATER_CLAIMS,
) -> tuple[PieceLookup, PieceRow]:
    lookup = await store.reusable(PieceAsk(QUESTION, AJRAKH, ("GEOGRAPHY",), depth, fresh=True))
    answer_id = await answer_row(session)
    block = await prose_of(session, claims)
    await store.keep(lookup, answer_id=answer_id, depth=depth, sections=[BuiltSection("GEOGRAPHY", (block,))])
    row = await session.scalar(select(PieceRow).where(PieceRow.createdFromAnswerId == answer_id))
    assert row is not None
    await session.refresh(row)
    return lookup, row


async def reused_ids(store: SqlPieceStore, depth: str = "EXPERT") -> list[uuid.UUID]:
    lookup = await store.reusable(PieceAsk(QUESTION, AJRAKH, ("GEOGRAPHY",), depth))
    section = lookup.reused.get("GEOGRAPHY")
    return [piece.id for piece in section.pieces] if section else []


async def test_a_kept_piece_is_stored_with_what_it_rests_on_and_reused_for_the_same_question(
    session: AsyncSession,
) -> None:
    store = store_for(session)
    lookup, row = await kept(session, store)
    assert lookup.topics["GEOGRAPHY"].startswith("water:")
    assert (row.kind, row.facet, row.topicKey, row.depth, row.language) == (
        "prose",
        "GEOGRAPHY",
        lookup.topics["GEOGRAPHY"],
        "EXPERT",
        "en",
    )
    assert row.claimIds == sorted(WATER_CLAIMS)
    body = {key: value for key, value in row.payload.items() if key not in ("id", "reuse")}
    canonical = json.dumps(body, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    assert row.contentHash == hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    assert row.embedding is not None and row.staleSince is None
    assert await reused_ids(store) == [row.id]


@pytest.mark.parametrize(
    "change",
    [
        {"status": "RETRACTED"},
        {"status": "DRAFT"},
        {"evidenceLevel": "REVIEWED"},
        {"text": "The water of Kutch is said to be hard."},
        {"sensitivity": "RESTRICTED"},
    ],
)
async def test_a_claim_change_stales_every_piece_resting_on_it(session: AsyncSession, change: dict) -> None:
    store = store_for(session)
    _, row = await kept(session, store)
    await session.execute(update(Claim).where(Claim.id == WATER_CLAIMS[0]).values(**change))
    await session.refresh(row)
    assert row.staleSince is not None
    assert await reused_ids(store) == []


async def test_filling_a_claim_vector_does_not_stale_a_piece(session: AsyncSession) -> None:
    store = store_for(session)
    _, row = await kept(session, store)
    vector = [0.0] * (DIMENSIONS - 1) + [1.0]
    await session.execute(update(Claim).where(Claim.id == WATER_CLAIMS[0]).values(embedding=vector))
    await session.refresh(row)
    assert row.staleSince is None
    assert await reused_ids(store) == [row.id]


async def test_a_rebuilt_piece_supersedes_the_stale_one_and_is_reused(session: AsyncSession) -> None:
    store = store_for(session)
    _, old = await kept(session, store)
    await session.execute(update(Claim).where(Claim.id == WATER_CLAIMS[2]).values(status="RETRACTED"))
    _, new = await kept(session, store, claims=WATER_CLAIMS[:2])
    await session.refresh(old)
    assert (old.staleSince is not None, old.supersededById) == (True, new.id)
    assert new.claimIds == sorted(WATER_CLAIMS[:2])
    assert await reused_ids(store) == [new.id]


async def test_a_basic_piece_is_not_reused_for_an_expert_ask(session: AsyncSession) -> None:
    store = store_for(session)
    _, basic = await kept(session, store, depth="BASIC")
    assert await reused_ids(store, "EXPERT") == []
    assert await reused_ids(store, "BASIC") == [basic.id]


async def test_fresh_research_names_the_topics_but_reuses_nothing(session: AsyncSession) -> None:
    store = store_for(session)
    lookup, _ = await kept(session, store)
    fresh = await store.reusable(PieceAsk(QUESTION, AJRAKH, ("GEOGRAPHY",), "EXPERT", fresh=True))
    assert (fresh.topics, fresh.reused) == (lookup.topics, {})


async def test_a_piece_kept_while_embeddings_fail_is_filled_later(session: AsyncSession) -> None:
    _, row = await kept(session, store_for(session, embed=failing_embedder))
    assert row.embedding is None
    assert await embed_pieces(session, fixed_embedder, piece_ids=[row.id]) == 1
    await session.refresh(row)
    assert row.embedding is not None


async def craft_without_process(session: AsyncSession) -> Craft:
    craft = await session.scalar(
        select(Craft).where(~exists().where(Process.craftId == Craft.id)).order_by(Craft.slug).limit(1)
    )
    assert craft is not None
    return craft


async def stage_claim(session: AsyncSession, craft: Craft, name: str) -> uuid.UUID:
    concept = Concept(id=uuid.uuid4(), craftId=craft.id, type="PROCESS_STAGE", name=name)
    source = Source(
        id=uuid.uuid4(), kind="WEB_PAGE", title=f"{name} notes", url="https://crafts.example.org/stage"
    )
    claim = Claim(
        id=uuid.uuid4(),
        subjectType="CONCEPT",
        subjectId=concept.id,
        predicate="states",
        text=f"{name} comes before the next stage.",
        evidenceLevel="PROVISIONAL",
        origin="LIVE_RESEARCH",
    )
    session.add_all([concept, source, claim])
    await session.flush()
    session.add(
        ClaimSource(claimId=claim.id, sourceId=source.id, quote=f"{name} comes before the next stage")
    )
    await session.flush()
    return claim.id


async def test_cited_stage_concepts_never_become_a_process_of_their_own(session: AsyncSession) -> None:
    craft = await craft_without_process(session)
    claims = [
        await stage_claim(session, craft, "Washing the cloth"),
        await stage_claim(session, craft, "Printing the resist"),
    ]
    block = await prose_of(session, claims)
    ref = CraftRef(slug=craft.slug, name=craft.name, path=f"/crafts/{craft.slug}")
    store = store_for(session)
    lookup = await store.reusable(PieceAsk("How is it made?", ref, ("PROCESS",), "EXPERT", fresh=True))
    answer_id = await answer_row(session)
    await store.keep(
        lookup, answer_id=answer_id, depth="EXPERT", sections=[BuiltSection("PROCESS", (block,))]
    )
    piece = await session.scalar(select(PieceRow).where(PieceRow.createdFromAnswerId == answer_id))
    assert piece is not None and (piece.craftId, piece.facet) == (craft.id, "PROCESS")
    assert (await session.scalars(select(Process.id).where(Process.craftId == craft.id))).all() == []
    concepts = select(Claim.subjectId).where(Claim.id.in_(claims))
    assert (
        await session.scalars(select(ProcessStage.id).where(ProcessStage.conceptId.in_(concepts)))
    ).all() == []


async def stale_geography_piece(session: AsyncSession) -> PieceRow:
    asker = User(
        id=uuid.uuid4(),
        email=f"asker-{uuid.uuid4().hex[:8]}@example.com",
        name="Meera Rao",
        role="RESEARCHER",
    )
    session.add(asker)
    await session.flush()
    for _ in range(2):
        await answer_row(session, user_id=asker.id)
    store = store_for(session)
    _, row = await kept(session, store)
    await session.execute(
        update(PieceRow)
        .where(PieceRow.id == row.id)
        .values(createdFromAnswerId=await answer_row(session, user_id=asker.id))
    )
    await session.execute(update(Claim).where(Claim.id == WATER_CLAIMS[0]).values(evidenceLevel="REVIEWED"))
    return row


async def geography_groups(session: AsyncSession, now: datetime) -> list[StaleGroup]:
    groups = await stale_groups(session, now=now)
    return [group for group in groups if group.craft.slug == AJRAKH.slug and group.facet == "GEOGRAPHY"]


async def test_stale_pieces_of_asked_crafts_are_listed_for_the_nightly_rebuild(session: AsyncSession) -> None:
    row = await stale_geography_piece(session)
    found = await geography_groups(session, datetime.now(UTC))
    assert found and found[0].question == QUESTION and found[0].depth == "EXPERT"
    assert found[0].asks >= 3 and found[0].withheld_terms == ("Meera Rao",)
    assert row.id in found[0].piece_ids


async def test_a_group_tried_in_the_last_week_waits_a_week_before_it_is_tried_again(
    session: AsyncSession,
) -> None:
    row = await stale_geography_piece(session)
    now = datetime.now(UTC)
    (group,) = await geography_groups(session, now)
    assert await mark_rebuild_tried(session, group, now=now) == len(group.piece_ids)
    assert await session.scalar(select(PieceRow.rebuildTriedAt).where(PieceRow.id == row.id)) == now
    assert await geography_groups(session, now + timedelta(days=6)) == []
    assert [found.piece_ids for found in await geography_groups(session, now + timedelta(days=8))] == [
        group.piece_ids
    ]


async def test_a_stored_ladder_is_reused_only_while_it_matches_the_process_rows(
    session: AsyncSession,
) -> None:
    craft = await knowledge_view.resolve_craft(session, AJRAKH.slug)
    records = await process_records(session, craft)
    built = [
        (stage.id, process_ladder(records, block_id="s1.b1", stage_ids=[stage.id]))
        for stage in records.stages
    ]
    stage_id, ladder = next((found for found in built if found[1] is not None), (None, None))
    assert ladder is not None
    store = store_for(session)
    lookup = await store.reusable(PieceAsk(QUESTION, AJRAKH, ("PROCESS",), "EXPERT", fresh=True))
    answer_id = await answer_row(session)
    await store.keep(
        lookup, answer_id=answer_id, depth="EXPERT", sections=[BuiltSection("PROCESS", (ladder,))]
    )
    found = await store.reusable(PieceAsk(QUESTION, AJRAKH, ("PROCESS",), "EXPERT"))
    assert [piece.kind for piece in found.reused["PROCESS"].pieces] == ["process_ladder"]
    await session.execute(
        update(ProcessStage).where(ProcessStage.id == stage_id).values(name="Renamed stage")
    )
    again = await store.reusable(PieceAsk(QUESTION, AJRAKH, ("PROCESS",), "EXPERT"))
    assert "PROCESS" not in again.reused


async def curated_piece(session: AsyncSession, claims: Sequence[uuid.UUID]) -> uuid.UUID:
    store = store_for(session)
    lookup = await store.reusable(PieceAsk(QUESTION, AJRAKH, ("GEOGRAPHY",), "EXPERT", fresh=True))
    craft = await knowledge_view.resolve_craft(session, AJRAKH.slug)
    assert craft is not None
    slot = PieceSlot(craft.id, "GEOGRAPHY", lookup.topics["GEOGRAPHY"], "EXPERT")
    block = await prose_of(session, claims)
    piece = knowledge_piece(
        block, slot, piece_id=uuid.uuid4(), answer_id=None, created_at=datetime(2026, 11, 1, tzinfo=UTC)
    )
    session.add(PieceRow(**piece_values(piece)))
    for n, claim in enumerate(claims, start=1):
        session.add(CuratedClaim(claimId=claim, craftId=craft.id, key=f"C9{n:02d}", discipline="GEOGRAPHY"))
    await session.flush()
    return piece.id


async def test_an_answer_never_supersedes_a_curated_piece_and_is_reused_before_it(
    session: AsyncSession,
) -> None:
    curated = await curated_piece(session, WATER_CLAIMS[:2])
    store = store_for(session)
    _, row = await kept(session, store)
    stored = await session.get(PieceRow, curated)
    assert stored is not None
    await session.refresh(stored)
    assert stored.supersededById is None
    assert await reused_ids(store) == [row.id]
    await session.execute(update(Claim).where(Claim.id == WATER_CLAIMS[2]).values(status="RETRACTED"))
    assert await reused_ids(store) == [curated]


async def test_a_piece_whose_answer_was_deleted_is_superseded_like_any_reader_s(
    session: AsyncSession,
) -> None:
    store = store_for(session)
    _, first = await kept(session, store)
    await session.execute(delete(Answer).where(Answer.id == first.createdFromAnswerId))
    await session.refresh(first)
    assert first.createdFromAnswerId is None
    _, second = await kept(session, store)
    await session.refresh(first)
    assert first.supersededById == second.id
