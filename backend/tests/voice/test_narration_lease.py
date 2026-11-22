import asyncio
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta

from app.providers.elevenlabs import TimedSpeech
from app.services.naming import narration_key
from app.voice.listen import listen_script
from app.voice.object_lease import LEASE_LEAF, ObjectLease

from .listen_fakes import LISTENED_AT, Listening, Narrations, ask, golden_explainer

WATER_CACHE_ID = "afef7e08b43bab3f5865d8204f6048a8e5eaeb12dc9bc12c478fbc88d7b5218b"
LEASE_KEY = narration_key(WATER_CACHE_ID, LEASE_LEAF)


@dataclass
class GatedNarrations(Narrations):
    gate: asyncio.Event = field(default_factory=asyncio.Event)

    async def narration(
        self, text: str, *, voice_id: str, language: str, previous_text: str = "", next_text: str = ""
    ) -> TimedSpeech:
        await self.gate.wait()
        return await super().narration(
            text, voice_id=voice_id, language=language, previous_text=previous_text, next_text=next_text
        )


def leased(listening: Listening, taken_at: datetime) -> None:
    lease = ObjectLease(schema_version=1, cache_id=WATER_CACHE_ID, taken_at=taken_at)
    listening.objects.stored[LEASE_KEY] = (lease.model_dump_json(by_alias=True).encode(), "application/json")


async def test_a_second_reader_missing_the_same_block_waits_for_the_first_and_pays_nothing() -> None:
    narrator = GatedNarrations()
    listening = Listening(narrator=narrator)
    first = asyncio.create_task(listen_script(ask(golden_explainer(), "s2", request=1), listening.deps()))
    for _ in range(100):
        if LEASE_KEY in listening.objects.stored:
            break
        await asyncio.sleep(0)
    waits: list[float] = []

    async def wait_for_the_first(seconds: float) -> None:
        waits.append(seconds)
        narrator.gate.set()
        await first

    second = replace(listening.deps(), sleep=wait_for_the_first)
    heard = await listen_script(ask(golden_explainer(), "s2", request=2), second)
    assert heard == await first
    assert (len(narrator.calls), waits) == (1, [1.0])
    assert {row.key for row in listening.ledger.rows} == {
        "listen:00000000-0000-0000-0000-000000000001:hold",
        "listen-refund:00000000-0000-0000-0000-000000000001",
    }
    assert LEASE_KEY not in listening.objects.stored


async def test_a_lapsed_lease_is_taken_over_and_released() -> None:
    listening = Listening()
    leased(listening, LISTENED_AT - timedelta(seconds=121))
    await listen_script(ask(golden_explainer(), "s2"), listening.deps())
    assert len(listening.narrator.calls) == 1
    assert LEASE_KEY not in listening.objects.stored


async def test_a_lease_whose_reader_never_finishes_is_waited_out_then_made_here() -> None:
    listening = Listening()
    leased(listening, LISTENED_AT)
    moments = [LISTENED_AT]

    async def tick(seconds: float) -> None:
        moments.append(moments[-1] + timedelta(seconds=seconds))

    deps = replace(listening.deps(), clock=lambda: moments[-1], sleep=tick)
    await listen_script(ask(golden_explainer(), "s2"), deps)
    assert (len(moments) - 1, len(listening.narrator.calls)) == (120, 1)
    assert LEASE_KEY not in listening.objects.stored
