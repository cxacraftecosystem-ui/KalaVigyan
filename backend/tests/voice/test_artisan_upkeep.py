import base64
import json
import uuid
from datetime import datetime, timedelta
from typing import Any

import pytest

from app.voice import artisan_upkeep
from app.voice.artisan_upkeep import ArtisanUpkeep, run_artisan_upkeep
from app.voice.privacy import TranscriptCipher

from .artisan_fakes import (
    CONVERSATION_ID,
    MemoryArtisanStore,
    artisan_turn as said,
    conversation,
    kalavigyan_turn as asked,
    sealed,
)
from .fakes import START, FakeModel, cipher

NOW = START + timedelta(days=1)
SOAK = "We soak the cloth in camel dung and castor oil before printing"
EARLIER_KEY = base64.urlsafe_b64encode(b"another-voice-transcript-key-32b").decode("ascii")


class LapsedStore(MemoryArtisanStore):
    async def unfinished(self, now: datetime, limit: int) -> list[uuid.UUID]:
        return [c.id for c in self.conversations.values() if c.ended_at is None][:limit]


class Session:
    async def commit(self) -> None:
        return None

    async def __aenter__(self) -> Session:
        return self

    async def __aexit__(self, *_: Any) -> None:
        return None


class Objects:
    async def delete(self, key: str) -> None:
        return None


@pytest.fixture
def database_steps(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    calls: list[str] = []

    async def purged(session: Any, objects: Any, *, now: Any) -> int:
        calls.append("purge")
        return 2

    async def cleared(session: Any, *, now: Any) -> int:
        calls.append("clear")
        return 1

    monkeypatch.setattr(artisan_upkeep, "purge_due", purged)
    monkeypatch.setattr(artisan_upkeep, "clear_expired_rejections", cleared)
    return calls


def upkeep(store: MemoryArtisanStore, model: FakeModel) -> ArtisanUpkeep:
    return ArtisanUpkeep(
        artisans=store,
        sessions=Session,
        objects=Objects(),
        cipher=cipher(),
        model_for=lambda *_: model,
    )


async def test_the_upkeep_retries_a_failed_extraction_once_and_purges_and_clears(
    database_steps: list[str],
) -> None:
    store = MemoryArtisanStore()
    item = {
        "turn": 1,
        "quote": SOAK,
        "english": SOAK,
        "claim": "The cloth is soaked in camel dung and castor oil before printing.",
        "discipline": "PROCESS",
        "conceptType": "PROCESS_STAGE",
        "conceptName": "Soaking",
    }
    store.conversations[CONVERSATION_ID] = conversation(
        transcript=sealed(asked(0, "How do you begin?"), said(1, SOAK)),
        ended_at=START,
        extraction="FAILED",
        attempts=1,
    )
    report = await run_artisan_upkeep(
        upkeep(store, FakeModel([json.dumps({"contributions": [item]})])), now=NOW
    )
    assert (report.extracted, report.purged, report.cleared) == (1, 2, 1)
    assert store.conversations[CONVERSATION_ID].extraction == "DONE"
    assert database_steps == ["purge", "clear"]


async def test_a_conversation_that_failed_twice_is_left_for_a_person(database_steps: list[str]) -> None:
    store = MemoryArtisanStore()
    store.conversations[CONVERSATION_ID] = conversation(
        transcript=sealed(asked(0, "How do you begin?")), ended_at=START, extraction="FAILED", attempts=2
    )
    model = FakeModel([])
    report = await run_artisan_upkeep(upkeep(store, model), now=NOW)
    assert report.extracted == 0 and model.calls == []


async def test_without_a_transcript_key_only_the_database_steps_run(database_steps: list[str]) -> None:
    store = MemoryArtisanStore()
    store.conversations[uuid.uuid4()] = conversation(ended_at=START, extraction="PENDING")
    chosen = upkeep(store, FakeModel([]))
    report = await run_artisan_upkeep(
        ArtisanUpkeep(chosen.artisans, chosen.sessions, chosen.objects, None, chosen.model_for), now=NOW
    )
    assert report.extracted == 0 and database_steps == ["purge", "clear"]


async def test_a_transcript_that_does_not_open_is_reported_and_the_rest_of_the_upkeep_still_runs(
    database_steps: list[str],
) -> None:
    store = LapsedStore()
    unreadable, quiet = uuid.UUID(int=41), uuid.UUID(int=42)
    store.conversations[unreadable] = conversation(
        id=unreadable,
        transcript=sealed(asked(0, "How do you begin?"), said(1, SOAK), key=TranscriptCipher(EARLIER_KEY)),
    )
    store.conversations[quiet] = conversation(id=quiet, transcript=sealed(asked(0, "How do you begin?")))
    report = await run_artisan_upkeep(upkeep(store, FakeModel([])), now=NOW)
    assert report.failures == [
        f"{unreadable}: The stored voice transcript does not open with the current key"
    ]
    assert (report.closed, report.purged, report.cleared) == (1, 2, 1)
    assert (store.conversations[quiet].ended_at, store.conversations[quiet].extraction) == (NOW, "NONE")
    assert store.conversations[unreadable].ended_at is None
    assert database_steps == ["purge", "clear"]
