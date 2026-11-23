import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db import get_engine
from app.models import Answer, Claim, ConsentRecord, Conversation, QuotaLedger, User
from app.research.crafts import CraftRef
from app.research.retrieval import OPEN_CHUNK_ACLS, chunk_acls_for
from app.services.claim_seed import seed_id
from app.voice.records import AnswerRecord, SessionRecord, TurnHold, TurnSave
from app.voice.seconds import ledger_entry, refund_key
from app.voice.store import SqlVoiceStore

from ..voice.fakes import session as voice_session
from .closed_quotes import CLOSED_QUOTE, quote_closed, store_closed_sources

pytestmark = pytest.mark.db

NOW = datetime.now(UTC).replace(microsecond=0)
AJRAKH = CraftRef(slug="Kutch-Ajrakh", name="Kutch Ajrakh", path="/crafts/Kutch-Ajrakh")
ALUM = "Alum is used as a mordant to fasten the colours."
CLOSED_FACT = "Alum from a closed monograph brightens the madder red in the second bath."
Stores = tuple[SqlVoiceStore, AsyncSession]


@pytest.fixture
async def store() -> AsyncIterator[Stores]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            factory = async_sessionmaker(
                bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
            )
            async with factory() as session:
                yield SqlVoiceStore(factory), session
        finally:
            await transaction.rollback()


async def learner(session: AsyncSession) -> User:
    user = User(id=uuid.uuid4(), name="Voice Learner", email=f"voice-{uuid.uuid4().hex[:8]}@example.com")
    session.add(user)
    await session.commit()
    return user


def live(user: User, **changes: object) -> SessionRecord:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "user_id": user.id,
        "chat_id": uuid.uuid4(),
        "craft": AJRAKH,
        "started_at": NOW,
        "expires_at": NOW + timedelta(seconds=120),
    }
    return voice_session(**{**defaults, **changes})


async def test_a_created_session_reads_back_with_its_role_and_craft(store: Stores) -> None:
    voice, session = store
    user = await learner(session)
    record = live(user)
    assert await voice.create(record)
    found = await voice.by_id(record.id)
    assert found is not None
    assert (found.role, found.craft, found.transport, found.max_duration_seconds) == (
        "STUDENT",
        AJRAKH,
        "RELAY",
        540,
    )
    assert found.retention_until == record.hard_end + timedelta(days=30)
    chat = await session.get(Conversation, record.chat_id)
    assert chat is not None and chat.channel == "VOICE"


async def test_one_live_session_per_user_is_held_by_the_index(store: Stores) -> None:
    voice, session = store
    user = await learner(session)
    assert await voice.create(live(user))
    assert not await voice.create(live(user))
    assert await voice.has_live(user.id, NOW) and await voice.live_count(NOW) >= 1


async def test_a_lapsed_session_is_closed_at_its_hard_end(store: Stores) -> None:
    voice, session = store
    user = await learner(session)
    old = live(user, started_at=NOW - timedelta(hours=1), expires_at=NOW - timedelta(minutes=58))
    await voice.create(old)
    assert await voice.close_lapsed(NOW) >= 1
    closed = await voice.by_id(old.id)
    assert closed is not None and closed.ended_at == old.hard_end and closed.nonce_hash is None
    assert closed.retention_until == old.hard_end + timedelta(days=30)


async def test_a_bound_session_is_found_by_its_conversation(store: Stores) -> None:
    voice, session = store
    user = await learner(session)
    record = live(user, transport="AGENT")
    await voice.create(record)
    await voice.bind(record.id, conversation_id="conv_db_test", agent_id="agent_test", nonce_hash="a" * 64)
    found = await voice.by_conversation("conv_db_test")
    assert found is not None and (found.id, found.nonce_hash, found.agent_id) == (
        record.id,
        "a" * 64,
        "agent_test",
    )


async def test_turns_stop_at_forty_and_after_the_end(store: Stores) -> None:
    voice, session = store
    user = await learner(session)
    record = live(user)
    await voice.create(record)
    begun = await voice.begin_turn(record.id, NOW)
    assert begun is not None and begun.turn_count == 1
    await voice.end(record.id, NOW + timedelta(seconds=10))
    assert await voice.begin_turn(record.id, NOW + timedelta(seconds=11)) is None


async def test_seconds_are_reserved_once_per_key_and_counted_today(store: Stores) -> None:
    voice, session = store
    user = await learner(session)
    record = live(user)
    await voice.create(record)
    entry = ledger_entry(record, units=12, key=f"voice:{record.id}:1")
    assert await voice.reserve(record.id, entry) == 12
    assert await voice.reserve(record.id, entry) == 12
    assert await voice.seconds_used(user.id, NOW) == 12


async def test_a_saved_turn_keeps_the_transcript_answer_and_seconds_together(store: Stores) -> None:
    voice, session = store
    user = await learner(session)
    record = live(user)
    await voice.create(record)
    answer = AnswerRecord(
        id=uuid.uuid4(), craft_slug=AJRAKH.slug, claim_ids=(), sentences=({"text": ALUM},), latency_ms=900
    )
    seconds = (ledger_entry(record, units=6, key=f"voice:{record.id}:t:speech"),)
    await voice.save_turn(
        record.id, TurnSave(merge=lambda current: "sealed-1", answer=answer, seconds=seconds)
    )
    await voice.save_turn(record.id, TurnSave(merge=lambda current: f"{current}+2"))
    found = await voice.by_id(record.id)
    assert found is not None and found.transcript == "sealed-1+2" and found.reserved_seconds == 6
    row = await session.get(Answer, answer.id)
    assert row is not None and row.conversationId == record.chat_id and row.question == "Voice turn"


async def test_ending_a_relay_session_bills_what_was_reserved(store: Stores) -> None:
    voice, session = store
    user = await learner(session)
    record = live(user)
    await voice.create(record)
    await voice.reserve(record.id, ledger_entry(record, units=9, key=f"voice:{record.id}:a"))
    ended = await voice.end(record.id, NOW + timedelta(seconds=45))
    assert ended is not None and ended.ended_at == NOW + timedelta(seconds=45) and ended.billed_seconds == 9
    again = await voice.end(record.id, NOW + timedelta(seconds=99))
    assert again is not None and again.ended_at == ended.ended_at


async def test_expired_transcripts_are_purged_and_agent_calls_settled(store: Stores) -> None:
    voice, session = store
    user = await learner(session)
    record = live(user, transport="AGENT")
    await voice.create(record)
    await voice.bind(record.id, conversation_id="conv_db_settle", agent_id="agent_test", nonce_hash="b" * 64)
    await voice.save_turn(record.id, TurnSave(merge=lambda current: "sealed"))
    await voice.reserve(record.id, ledger_entry(record, units=50, key=f"voice:{record.id}:1"))
    await voice.end(record.id, NOW + timedelta(seconds=60))
    [waiting] = [r for r in await voice.unreconciled(200) if r.id == record.id]
    refund = ledger_entry(waiting, units=-8, key=refund_key(record.id))
    await voice.settle(waiting, 42, refund)
    assert (await voice.by_id(record.id)).billed_seconds == 42
    assert await voice.seconds_used(user.id, NOW) == 42
    assert await voice.purge_transcripts(NOW + timedelta(days=31)) >= 1
    assert (await voice.by_id(record.id)).transcript is None
    rows = (await session.scalars(select(QuotaLedger).where(QuotaLedger.userId == user.id))).all()
    assert sorted(row.idempotencyKey for row in rows) == sorted(
        [f"voice:{record.id}:1", refund_key(record.id)]
    )


async def test_a_settlement_counts_on_the_day_its_call_started(store: Stores) -> None:
    voice, session = store
    user = await learner(session)
    yesterday = NOW - timedelta(days=1)
    record = live(
        user, transport="AGENT", started_at=yesterday, expires_at=yesterday + timedelta(seconds=120)
    )
    await voice.create(record)
    await voice.reserve(record.id, ledger_entry(record, units=20, key=f"voice:{record.id}:today"))
    refund = ledger_entry(record, units=-8, key=refund_key(record.id))
    await voice.settle(record, 42, refund)
    await voice.settle(record, 42, refund)
    row = await session.scalar(select(QuotaLedger).where(QuotaLedger.idempotencyKey == refund_key(record.id)))
    assert row is not None and row.createdAt == yesterday and row.units == -8
    assert await voice.seconds_used(user.id, NOW) == 20


async def test_consent_is_read_by_version(store: Stores) -> None:
    voice, session = store
    user = await learner(session)
    session.add(
        ConsentRecord(userId=user.id, kind="VOICE_NOTICE", noticeVersion="2026-11-16", acceptedAt=NOW)
    )
    await session.commit()
    assert await voice.consented(user.id, "2026-11-16")
    assert not await voice.consented(user.id, "2026-12-01")


async def test_the_claim_pack_holds_the_seeded_cited_claims(store: Stores) -> None:
    voice, _ = store
    pack = await voice.pack(AJRAKH, "HYBRID", OPEN_CHUNK_ACLS)
    alum = [view for view in pack.cited.views.values() if view.text == ALUM]
    assert alum and alum[0].citations
    assert all(cite["sourceId"] in pack.cited.sources for view in alum for cite in view.citations)
    assert pack.craft == AJRAKH and pack.mode == "HYBRID"


async def test_a_student_s_pack_cites_a_closed_page_without_its_words_and_a_researcher_s_quotes_it(
    store: Stores,
) -> None:
    voice, session = store
    await store_closed_sources(session)
    fact = Claim(
        id=uuid.uuid4(),
        subjectType="CONCEPT",
        subjectId=seed_id("concept", "ie:ajrakh.material.alum"),
        predicate="states",
        text=CLOSED_FACT,
        evidenceLevel="PROVISIONAL",
        origin="LIVE_RESEARCH",
    )
    session.add(fact)
    await session.flush()
    await quote_closed(session, [fact.id])
    await session.commit()
    student = await voice.pack(AJRAKH, "HYBRID", chunk_acls_for("STUDENT"))
    researcher = await voice.pack(AJRAKH, "HYBRID", chunk_acls_for("RESEARCHER"))
    assert [(c["quote"], c["evidence"]) for c in student.cited.views[fact.id].citations] == [
        (None, "INFERRED")
    ]
    assert [c["quote"] for c in researcher.cited.views[fact.id].citations] == [CLOSED_QUOTE]
    assert CLOSED_QUOTE not in repr(student.cited)


@pytest.mark.usefixtures("allowances_an_owner_might_set")
async def test_a_relay_turn_claim_holds_what_the_day_allows_and_counts_the_turn(store: Stores) -> None:
    voice, session = store
    user = await learner(session)
    record = live(user)
    await voice.create(record)
    await voice.reserve(record.id, ledger_entry(record, units=600 - 45, key=f"voice:{record.id}:earlier"))
    first = TurnHold(entry=ledger_entry(record, units=60, key=f"voice:{record.id}:turn-a"), least=10)
    claim = await voice.claim_turn(record.id, NOW, first)
    assert claim.held == 45 and claim.session is not None and claim.session.turn_count == 1
    second = TurnHold(entry=ledger_entry(record, units=60, key=f"voice:{record.id}:turn-b"), least=1)
    assert (await voice.claim_turn(record.id, NOW, second)).refusal == "quota"
    await voice.end(record.id, NOW + timedelta(seconds=5))
    assert (await voice.claim_turn(record.id, NOW + timedelta(seconds=6), second)).refusal == "ended"
    assert await voice.seconds_used(user.id, NOW) == 600


async def test_an_ended_agent_call_keeps_the_slot_until_settled_or_its_window_passes(store: Stores) -> None:
    voice, session = store
    user = await learner(session)
    record = live(user, transport="AGENT")
    await voice.create(record)
    await voice.bind(record.id, conversation_id="conv_db_slot", agent_id="agent_test", nonce_hash="c" * 64)
    await voice.end(record.id, NOW + timedelta(seconds=10))
    assert await voice.has_live(user.id, NOW + timedelta(seconds=20))
    assert not await voice.has_live(user.id, NOW + timedelta(seconds=120 + 600))
    [waiting] = await voice.unreconciled(5, user_id=user.id)
    await voice.settle(waiting, 30, None)
    assert not await voice.has_live(user.id, NOW + timedelta(seconds=20))
