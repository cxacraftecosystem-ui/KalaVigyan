import asyncio
from dataclasses import dataclass, field, replace
from datetime import timedelta

import pytest

from app.providers.elevenlabs import TimedSpeech
from app.services.naming import narration_key
from app.voice import listen_making
from app.voice.listen import listen_script
from app.voice.object_lease import LEASE_LEAF, held_lease

from .listen_fakes import LISTENED_AT, Listening, Narrations, ask, golden_explainer

FIRST_SPOKEN = "Outlines where white is required"
WATER_CACHE_ID = "bd3236e34f5b67779faf30fe17ff46f5d16cb08fe505d716dcf3ad79a493e882"
WATER_LEASE = narration_key(WATER_CACHE_ID, LEASE_LEAF)
FIRST_ASK = "00000000-0000-0000-0000-000000000001"


@dataclass
class HeldBack(Narrations):
    gate: asyncio.Event = field(default_factory=asyncio.Event)

    async def narration(
        self, text: str, *, voice_id: str, language: str, previous_text: str = "", next_text: str = ""
    ) -> TimedSpeech:
        if FIRST_SPOKEN not in text:
            await self.gate.wait()
        return await super().narration(
            text, voice_id=voice_id, language=language, previous_text=previous_text, next_text=next_text
        )


class Throttled(Exception):
    pass


async def test_the_first_block_is_heard_while_the_others_are_still_being_read() -> None:
    narrator = HeldBack()
    listening = Listening(narrator=narrator)
    first = await listen_script(ask(golden_explainer(), request=1), listening.deps())
    assert [track.block_id for track in first.tracks] == ["s1.b1"]
    assert (first.pending, first.poll_after_seconds) == (["s2.b1", "s3.b1"], 3)
    polled = await listen_script(ask(golden_explainer(), request=2), listening.deps())
    assert (polled.tracks, polled.pending) == (first.tracks, first.pending)
    assert [row.key for row in listening.ledger.rows] == [f"listen:{FIRST_ASK}:elevenlabs:hold"]
    narrator.gate.set()
    await listening.shield.drain()
    done = await listen_script(ask(golden_explainer(), request=3), listening.deps())
    assert [track.block_id for track in done.tracks] == ["s1.b1", "s2.b1", "s3.b1"]
    assert (done.pending, done.poll_after_seconds, done.tracks[0]) == ([], None, first.tracks[0])
    assert len(narrator.calls) == 3
    held, refund = listening.ledger.rows
    assert (held.units, refund.key, refund.units) == (
        75,
        f"listen-refund:{FIRST_ASK}:elevenlabs",
        -(75 - 33 - 15 - 16),
    )


async def test_only_an_ask_that_starts_a_making_is_admitted() -> None:
    admitted: list[str] = []

    async def admit() -> None:
        admitted.append("making")

    listening = Listening()
    deps = replace(listening.deps(), admit=admit)
    await listen_script(ask(golden_explainer(), request=1), deps)
    await listening.shield.drain()
    await listen_script(ask(golden_explainer(), request=2), deps)
    assert admitted == ["making"]


async def test_a_refused_making_holds_nothing_reads_nothing_and_frees_its_leases() -> None:
    async def refuse() -> None:
        raise Throttled

    listening = Listening()
    with pytest.raises(Throttled):
        await listen_script(ask(golden_explainer()), replace(listening.deps(), admit=refuse))
    assert (listening.ledger.rows, listening.narrator.calls) == ([], [])
    assert not any(key.endswith(LEASE_LEAF) for key in listening.objects.stored)


async def test_the_leases_of_blocks_still_being_read_are_renewed_until_each_is_made(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(listen_making, "LEASE_RENEW_SECONDS", 0.01)
    narrator = HeldBack()
    listening = Listening(narrator=narrator)
    moments = [LISTENED_AT]
    deps = replace(listening.deps(), clock=lambda: moments[-1])
    await listen_script(ask(golden_explainer()), deps)
    moments.append(LISTENED_AT + timedelta(seconds=100))
    renewed = None
    for _ in range(200):
        renewed = await held_lease(listening.objects, WATER_LEASE)
        if renewed is not None and renewed.taken_at == moments[-1]:
            break
        await asyncio.sleep(0.01)
    assert renewed is not None and renewed.taken_at == LISTENED_AT + timedelta(seconds=100)
    narrator.gate.set()
    await listening.shield.drain()
    assert WATER_LEASE not in listening.objects.stored
