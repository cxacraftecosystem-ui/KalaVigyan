import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.db import get_engine
from app.models import (
    AdminDistrict,
    AdminState,
    Answer,
    ArtisanContribution,
    ArtisanConversation,
    ArtisanConversationAudio,
    ArtisanCraft,
    ArtisanProfile,
    ConsentRecord,
    Craft,
    User,
    VoiceSession,
)
from app.research.crafts import CraftRef
from app.research.testimony import RECORDING_NOTICE_VERSION
from app.voice.artisan_records import AudioWrite, ContributionWrite, NewConversation, TurnWrite
from app.voice.artisan_store import SqlArtisanStore
from app.voice.records import AnswerRecord

from ..voice.fakes import session as voice_session

pytestmark = pytest.mark.db

NOW = datetime.now(UTC).replace(microsecond=0)
STATE_LGD = 24
DISTRICT_LGD = 449
Stores = tuple[SqlArtisanStore, AsyncSession]


@pytest.fixture
async def store() -> AsyncIterator[Stores]:
    async with get_engine().connect() as connection:
        transaction = await connection.begin()
        try:
            factory = async_sessionmaker(
                bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
            )
            async with factory() as session:
                yield SqlArtisanStore(factory), session
        finally:
            await transaction.rollback()


async def artisan(session: AsyncSession) -> tuple[User, Craft, ConsentRecord]:
    user = User(
        id=uuid.uuid4(),
        name="Ismail Khatri",
        email=f"artisan-{uuid.uuid4().hex[:8]}@example.com",
        role="ARTISAN",
    )
    craft = Craft(
        id=uuid.uuid4(), slug=f"Conversation-Test-{uuid.uuid4().hex[:8]}", name="Conversation Test Print"
    )
    await session.merge(AdminState(lgd=STATE_LGD, name="Gujarat"))
    await session.merge(AdminDistrict(lgd=DISTRICT_LGD, stateLgd=STATE_LGD, name="Kachchh"))
    session.add_all([user, craft])
    await session.flush()
    consent = ConsentRecord(
        userId=user.id, kind="ARTISAN_RECORDING", noticeVersion=RECORDING_NOTICE_VERSION, acceptedAt=NOW
    )
    session.add_all(
        [
            ArtisanProfile(
                userId=user.id,
                districtLgd=DISTRICT_LGD,
                spokenLanguage="gu",
                creditMode="FIRST_NAME",
                creditShortName="Ismail",
                adultConfirmedAt=NOW,
                completedAt=NOW,
            ),
            ArtisanCraft(userId=user.id, craftId=craft.id, position=1),
            consent,
        ]
    )
    await session.commit()
    return user, craft, consent


def new_conversation(user: User, craft: Craft, consent: ConsentRecord) -> NewConversation:
    ref = CraftRef(slug=craft.slug, name=craft.name, path=f"/crafts/{craft.slug}")
    record = voice_session(
        id=uuid.uuid4(),
        user_id=user.id,
        role="ARTISAN",
        craft=ref,
        mode="VERIFIED",
        chat_id=uuid.uuid4(),
        started_at=NOW,
        expires_at=NOW + timedelta(seconds=120),
        purpose="ARTISAN",
    )
    return NewConversation(
        session=record,
        conversation_id=uuid.uuid4(),
        craft_id=craft.id,
        consent_record_id=consent.id,
        consent_version=RECORDING_NOTICE_VERSION,
        transcript="sealed-opening",
        topics_asked=("PROCESS",),
    )


async def test_a_started_conversation_holds_an_artisan_voice_session_and_reads_back(store: Stores) -> None:
    artisans, session = store
    user, craft, consent = await artisan(session)
    new = new_conversation(user, craft, consent)
    assert await artisans.start(new)
    voice = await session.get(VoiceSession, new.session.id)
    assert voice is not None and voice.purpose == "ARTISAN" and voice.transcriptEnc is None
    found = await artisans.by_voice_session(new.session.id)
    assert found is not None and found.id == new.conversation_id
    assert (found.craft.slug, found.district, found.role, found.topics_asked) == (
        craft.slug,
        "Kachchh",
        "ARTISAN",
        ("PROCESS",),
    )
    facts = await artisans.facts(user.id)
    assert [ref.slug for _, ref in facts.crafts] == [craft.slug]
    assert facts.consent == (consent.id, RECORDING_NOTICE_VERSION)
    assert await artisans.held_back(user.id) == frozenset({"khatri"})


async def test_a_second_live_conversation_is_refused_by_the_one_live_session_rule(store: Stores) -> None:
    artisans, session = store
    user, craft, consent = await artisan(session)
    assert await artisans.start(new_conversation(user, craft, consent))
    assert not await artisans.start(new_conversation(user, craft, consent))


def spoken_turn(user: User, craft: Craft, turn_id: uuid.UUID, answer_id: uuid.UUID) -> TurnWrite:
    audio = AudioWrite(
        turn_id=turn_id,
        ordinal=1,
        object_key=f"media/{user.id}/{uuid.uuid4().hex}/T01.webm",
        mime_type="audio/webm",
        byte_count=10,
        duration_ms=4_000,
        start_ms=1_000,
    )
    answer = AnswerRecord(id=answer_id, craft_slug=craft.slug, claim_ids=(), sentences=(), latency_ms=0)
    return TurnWrite(
        merge=lambda sealed: f"{sealed}+turn",
        topics_asked=("PROCESS", "MATERIALS"),
        answer=answer,
        audio=audio,
    )


def soaking(turn_id: uuid.UUID) -> ContributionWrite:
    return ContributionWrite(
        turn_id=turn_id,
        ordinal=1,
        quote="We soak the cloth in camel dung first",
        english="We soak the cloth in camel dung first",
        english_source="ORIGINAL",
        claim_text="The cloth is soaked in camel dung first.",
        discipline="PROCESS",
        concept_type="PROCESS_STAGE",
        concept_name="Soaking",
        start_ms=1_000,
        end_ms=5_000,
        precision="TURN",
    )


async def test_turns_audio_answers_and_contributions_are_written_once_each(store: Stores) -> None:
    artisans, session = store
    user, craft, consent = await artisan(session)
    new = new_conversation(user, craft, consent)
    await artisans.start(new)
    turn_id, answer_id = uuid.uuid4(), uuid.uuid4()
    await artisans.save_turn(new.conversation_id, spoken_turn(user, craft, turn_id, answer_id))
    row = await session.get(ArtisanConversation, new.conversation_id, populate_existing=True)
    assert (
        row is not None
        and row.transcriptEnc == "sealed-opening+turn"
        and row.topicsAsked == ["PROCESS", "MATERIALS"]
    )
    assert (await session.scalars(select(ArtisanConversationAudio.turnId))).all() == [turn_id]
    assert (await session.get(Answer, answer_id)) is not None
    finished = await artisans.finish(new.conversation_id, NOW, spoke=True)
    assert finished is not None and finished.extraction == "PENDING"
    claimed = await artisans.claim_extraction(new.conversation_id, NOW)
    assert claimed is not None and (claimed.extraction, claimed.attempts) == ("RUNNING", 1)
    assert await artisans.claim_extraction(new.conversation_id, NOW) is None
    await artisans.save_extraction(new.conversation_id, "DONE", [soaking(turn_id)], NOW)
    [written] = (
        await session.scalars(
            select(ArtisanContribution).where(ArtisanContribution.conversationId == new.conversation_id)
        )
    ).all()
    assert (written.status, written.craftId, written.quoteLanguage) == ("PENDING", craft.id, "en")
    assert await artisans.due_extractions(10, max_attempts=2) == []
