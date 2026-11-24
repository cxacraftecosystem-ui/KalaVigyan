import json
import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.core.errors import ExternalFailure
from app.providers.budget import day_start
from app.providers.elevenlabs import NARRATION_MAX_CHARACTERS, NARRATION_MODEL, TimedSpeech
from app.schemas.listen import ListenScript
from app.services.explainer_payload import stored_explainer
from app.voice.listen import NARRATION_LINK_SECONDS, listen_script
from app.voice.listen_ask import ListenRefused
from app.voice.narration import PART_CHARACTERS

from ..contracts.golden import dumped, golden_json, golden_text
from .listen_fakes import (
    BUCKET_HOST,
    LISTENED_AT,
    Listening,
    MemoryLedger,
    Narrations,
    ask,
    golden_explainer,
)

WATER_CHARACTERS = 294
CHEMISTRY_CHARACTERS = 312
LADDER_CHARACTERS = 643


async def test_a_cache_hit_makes_no_second_text_to_speech_call() -> None:
    listening = Listening()
    first = await listen_script(ask(golden_explainer(), request=1), listening.deps())
    await listening.shield.drain()
    assert len(listening.narrator.calls) == 3
    rows = list(listening.ledger.rows)
    again = await listen_script(ask(golden_explainer(), request=2), listening.deps())
    assert len(listening.narrator.calls) == 3
    assert listening.ledger.rows == rows
    assert (first.tracks, first.pending) == (again.tracks[:1], ["s2.b1", "s3.b1"])
    assert (again.pending, again.poll_after_seconds) == ([], None)


async def test_every_spoken_block_becomes_a_track_with_a_private_link() -> None:
    listening = Listening()
    script = await listening.whole(ask(golden_explainer()))
    assert [track.block_id for track in script.tracks] == ["s1.b1", "s2.b1", "s3.b1"]
    for track in script.tracks:
        assert track.audio_url.startswith(f"{BUCKET_HOST}/media/narration/")
        assert track.audio_url.endswith(f".mp3?X-Amz-Expires={NARRATION_LINK_SECONDS}")
    stored = {key: kind for key, (_, kind) in listening.objects.stored.items()}
    assert sorted(set(stored.values())) == ["application/json", "audio/mpeg"]
    assert sum(1 for kind in stored.values() if kind == "audio/mpeg") == 3


async def test_the_narration_is_asked_for_in_the_explainer_s_language_with_the_narration_model() -> None:
    listening = Listening()
    await listen_script(ask(golden_explainer(), "s2"), listening.deps())
    [call] = listening.narrator.calls
    assert call["language"] == "en" and call["voiceId"] == "voice_1"
    assert call["text"].startswith("Presence of iron in the water supply")
    assert len(call["text"]) == WATER_CHARACTERS
    assert NARRATION_MODEL == "eleven_v4"


async def test_a_miss_holds_the_estimate_then_refunds_what_the_audio_did_not_use() -> None:
    listening = Listening()
    await listen_script(ask(golden_explainer(), "s3", request=7), listening.deps())
    await listening.shield.drain()
    held, refund = listening.ledger.rows
    assert (held.key, held.units, held.resource) == (
        "listen:00000000-0000-0000-0000-000000000007:elevenlabs:hold",
        19,
        "VOICE_SECONDS",
    )
    assert (refund.key, refund.units) == ("listen-refund:00000000-0000-0000-0000-000000000007:elevenlabs", -3)
    assert (held.ref_type, held.ref_id) == ("Answer", str(golden_explainer().answer_id))


@dataclass
class PastMidnight(Narrations):
    moments: list[datetime] = field(default_factory=list)
    late: datetime | None = None

    async def narration(self, text: str, **asked: Any) -> TimedSpeech:
        if self.late is not None:
            self.moments.append(self.late)
        return await super().narration(text, **asked)


async def test_a_hold_taken_before_midnight_is_refunded_to_its_own_day() -> None:
    held_at = datetime(2026, 11, 17, 18, 29, 30, tzinfo=UTC)
    settled_at = held_at + timedelta(minutes=1)
    assert day_start(settled_at) - day_start(held_at) == timedelta(days=1)
    moments = [held_at]
    listening = Listening(narrator=PastMidnight(moments=moments, late=settled_at))
    deps = replace(listening.deps(), clock=lambda: moments[-1])
    await listen_script(ask(golden_explainer(), "s3", request=7), deps)
    await listening.shield.drain()
    held, refund = listening.ledger.rows
    assert moments[-1] == settled_at
    assert (held.counted_at, refund.counted_at, refund.units) == (held_at, held_at, -3)


async def test_audio_longer_than_its_estimate_is_settled_within_what_is_left() -> None:
    listening = Listening(ledger=MemoryLedger(allowance=40, used=0))
    listening.narrator.seconds_per_character = 0.1
    await listen_script(ask(golden_explainer(), "s3", request=8), listening.deps())
    await listening.shield.drain()
    held, settled = listening.ledger.rows
    assert (held.units, settled.key, settled.units) == (
        19,
        "listen-settle:00000000-0000-0000-0000-000000000008:elevenlabs",
        13,
    )
    assert held.counted_at == settled.counted_at == LISTENED_AT


async def test_not_enough_seconds_left_refuses_before_any_speech_until_midnight() -> None:
    listening = Listening(ledger=MemoryLedger(allowance=600, used=590))
    with pytest.raises(ListenRefused) as refused:
        await listen_script(ask(golden_explainer(), "s3"), listening.deps())
    assert refused.value.reason == "quota" and refused.value.retry_after == 34_200
    assert listening.narrator.calls == [] and listening.ledger.rows == []


async def test_a_master_admin_is_never_capped() -> None:
    listening = Listening(ledger=MemoryLedger(allowance=None, used=10**9))
    script = await listening.whole(ask(golden_explainer()))
    assert len(script.tracks) == 3
    assert WATER_CHARACTERS + CHEMISTRY_CHARACTERS + LADDER_CHARACTERS == 1249
    assert listening.ledger.rows[0].units == 75


async def test_cached_narration_plays_even_when_no_seconds_are_left() -> None:
    listening = Listening()
    await listen_script(ask(golden_explainer(), "s2"), listening.deps())
    listening.ledger.used = 10**6
    script = await listen_script(ask(golden_explainer(), "s2", request=2), listening.deps())
    assert [track.block_id for track in script.tracks] == ["s2.b1"]


async def test_a_long_answer_is_spoken_in_parts_within_the_provider_s_limit() -> None:
    document = golden_json("explainer.document.golden.json")
    prose = document["sections"][1]["blocks"][0]
    cited = prose["sentences"]
    prose["sentences"] = [
        {
            **cited[(n - 1) % 3],
            "id": f"s2.b1.{n}",
            "text": f"Excess iron in groundwater threatened Ajrakh, part {n}. " * 7,
            "terms": [],
        }
        for n in range(1, 9)
    ]
    explainer = golden_explainer(sections=document["sections"])
    listening = Listening()
    script = await listen_script(ask(explainer, "s2"), listening.deps())
    texts = [call["text"] for call in listening.narrator.calls]
    assert len(texts) == 2 and all(len(text) <= PART_CHARACTERS <= NARRATION_MAX_CHARACTERS for text in texts)
    assert (
        listening.narrator.calls[1]["previous"] == texts[0]
        and listening.narrator.calls[0]["next"] == texts[1]
    )
    assert [track.block_id for track in script.tracks] == ["s2.b1", "s2.b1"]
    spoken = {word.sentence_id for track in script.tracks for word in track.words}
    assert spoken == {f"s2.b1.{n}" for n in range(1, 9)}


async def test_a_section_with_nothing_to_read_is_refused() -> None:
    with pytest.raises(ListenRefused) as refused:
        await listen_script(ask(golden_explainer(), "s9"), Listening().deps())
    assert refused.value.reason == "nothing"


async def test_a_later_block_that_fails_bills_only_the_audio_made_and_is_made_by_the_next_ask() -> None:
    listening = Listening()
    listening.narrator.failing = "Ajrakh colours come from indigo"
    heard = await listen_script(ask(golden_explainer(), None, request=3), listening.deps())
    await listening.shield.drain()
    assert ([track.block_id for track in heard.tracks], heard.pending) == (["s1.b1"], ["s2.b1", "s3.b1"])
    billed = sum(row.units for row in listening.ledger.rows)
    assert billed == 33 + 15
    retried = Listening(objects=listening.objects)
    again = await listen_script(ask(golden_explainer(), None, request=4), retried.deps())
    await retried.shield.drain()
    assert [track.block_id for track in again.tracks] == ["s1.b1", "s2.b1"] and again.pending == ["s3.b1"]
    assert [call["text"][:30] for call in retried.narrator.calls] == ["Ajrakh colours come from indig"]


async def test_a_first_block_that_fails_fails_the_ask_bills_the_audio_made_and_frees_every_lease() -> None:
    listening = Listening()
    listening.narrator.failing = "Outlines where white is required"
    with pytest.raises(ExternalFailure):
        await listen_script(ask(golden_explainer(), None, request=5), listening.deps())
    assert sum(row.units for row in listening.ledger.rows) == 15 + 16
    assert not any(key.endswith("lease.json") for key in listening.objects.stored)


async def test_the_listen_golden_is_reproduced_from_the_explainer_golden() -> None:
    script = await listen_script(ask(golden_explainer(), "s2"), Listening().deps())
    assert dumped(ListenScript, script) == golden_text("listen.script.golden.json")
    assert json.loads(golden_text("listen.script.golden.json"))["tracks"][0]["blockId"] == "s2.b1"


async def test_the_pending_golden_is_a_whole_answer_s_first_ask() -> None:
    script = await listen_script(ask(golden_explainer(), None, request=9), Listening().deps())
    assert dumped(ListenScript, script) == golden_text("listen.script-pending.golden.json")
    assert (script.pending, script.poll_after_seconds) == (["s2.b1", "s3.b1"], 3)


def test_only_the_answer_s_own_explainer_is_read_from_its_payload() -> None:
    document = golden_json("explainer.document.golden.json")
    own = golden_explainer().answer_id
    assert stored_explainer(own, {"explainer": document}) == golden_explainer()
    assert stored_explainer(uuid.UUID(int=3), {"explainer": document}) is None
    assert stored_explainer(own, {"channel": "VOICE", "sentences": []}) is None
    assert stored_explainer(own, None) is None
    assert stored_explainer(own, {"explainer": {**document, "sections": []}}) is None
    assert stored_explainer(own, {"explainer": "not a document"}) is None
