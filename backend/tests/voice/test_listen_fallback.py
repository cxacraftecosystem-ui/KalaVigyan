from dataclasses import dataclass, replace

import pytest

from app.core.errors import ExternalFailure, NotConfigured
from app.providers.elevenlabs import TimedSpeech
from app.research.explainer import Explainer
from app.schemas.listen import ListenScript
from app.voice.listen import listen_script
from app.voice.listen_ask import ListenRefused
from app.voice.listen_voices import listen_offer

from ..contracts.golden import dumped, golden_json, golden_text
from .listen_fakes import Listening, MemoryLedger, Narrations, ask, golden_explainer

REQUEST = "00000000-0000-0000-0000-000000000005"
EVERY_LANGUAGE = ["en", "hi", "bn", "ta", "te", "mr", "gu", "kn", "ml", "or", "pa", "as", "ur"]


@dataclass
class BucketRefusing(Narrations):
    async def narration(
        self, text: str, *, voice_id: str, language: str, previous_text: str = "", next_text: str = ""
    ) -> TimedSpeech:
        raise ExternalFailure("the bucket refused the narration", service="s3")


def both(listening: Listening) -> tuple:
    return (listening.elevenlabs(), listening.gemini())


async def test_when_elevenlabs_refuses_the_gemini_voice_reads_the_section_sentence_by_sentence() -> None:
    listening = Listening()
    listening.narrator.failing = "Presence of iron"
    script = await listen_script(ask(golden_explainer(), "s2", request=5), listening.deps(*both(listening)))
    await listening.shield.drain()
    assert dumped(ListenScript, script) == golden_text("listen.script-sentences.golden.json")
    assert [call["text"][:24] for call in listening.reader.calls] == [
        "Presence of iron in the ",
        "Ajrakh printing got conc",
        "Excess iron in groundwat",
    ]
    assert {call["voice"] for call in listening.reader.calls} == {"Kore"}
    assert [(row.key, row.units) for row in listening.ledger.rows] == [
        (f"listen:{REQUEST}:elevenlabs:hold", 18),
        (f"listen-refund:{REQUEST}:elevenlabs", -18),
        (f"listen:{REQUEST}:gemini:hold", 18),
        (f"listen-refund:{REQUEST}:gemini", -3),
    ]
    kinds = sorted({kind for _, kind in listening.objects.stored.values()})
    assert kinds == ["application/json", "audio/wav"]


async def test_a_section_the_gemini_voice_read_is_served_from_its_cache_the_next_time() -> None:
    listening = Listening()
    listening.narrator.failing = "Presence of iron"
    first = await listen_script(ask(golden_explainer(), "s2", request=5), listening.deps(listening.gemini()))
    await listening.shield.drain()
    rows = list(listening.ledger.rows)
    again = await listen_script(ask(golden_explainer(), "s2", request=6), listening.deps(listening.gemini()))
    assert again == first and listening.ledger.rows == rows and len(listening.reader.calls) == 3


async def test_a_failure_that_is_not_the_voice_s_own_is_not_read_again_by_another_voice() -> None:
    listening = Listening(narrator=BucketRefusing())
    with pytest.raises(ExternalFailure, match="bucket"):
        await listen_script(ask(golden_explainer(), "s2"), listening.deps(*both(listening)))
    assert listening.reader.calls == []


async def test_when_both_voices_fail_the_last_failure_is_raised() -> None:
    listening = Listening()
    listening.narrator.failing = "Presence of iron"
    listening.reader.failing = "Presence of iron"
    with pytest.raises(ExternalFailure) as failure:
        await listen_script(ask(golden_explainer(), "s2"), listening.deps(*both(listening)))
    assert failure.value.service == "gemini"
    assert sum(row.units for row in listening.ledger.rows) == 0


async def test_the_day_s_allowance_refuses_before_either_voice_speaks() -> None:
    listening = Listening(ledger=MemoryLedger(allowance=600, used=600))
    with pytest.raises(ListenRefused) as refused:
        await listen_script(ask(golden_explainer(), "s2"), listening.deps(*both(listening)))
    assert refused.value.reason == "quota"
    assert listening.narrator.calls == [] and listening.reader.calls == []


async def test_the_fallback_reads_the_lede_first_and_every_sentence_the_elevenlabs_voice_reads() -> None:
    answered = Explainer.model_validate(golden_json("explainer.lede.golden.json"))
    listening = Listening()
    elevenlabs = await listening.whole(ask(answered))
    gemini = await listening.whole(ask(answered, request=2), listening.deps(listening.gemini()))
    assert [t.block_id for t in gemini.tracks] == ["lede", "s1.b1", "s2.b1", "s3.b1"]
    assert [t.block_id for t in gemini.tracks] == [t.block_id for t in elevenlabs.tracks]
    heard = [word.sentence_id for track in elevenlabs.tracks for word in track.words]
    read = [sentence.sentence_id for track in gemini.tracks for sentence in track.sentences]
    assert read == list(dict.fromkeys(heard)) and gemini.voice == "GEMINI"


async def test_an_ask_that_names_its_voice_is_read_by_that_voice_alone() -> None:
    listening = Listening()
    named = ask(golden_explainer(), "s2", voice="GEMINI")
    script = await listen_script(named, listening.deps(*both(listening)))
    assert script.voice == "GEMINI" and listening.narrator.calls == []
    with pytest.raises(NotConfigured):
        await listen_script(
            ask(golden_explainer(), "s2", voice="ELEVENLABS"), listening.deps(listening.gemini())
        )


async def test_no_voice_for_the_language_is_not_configured() -> None:
    listening = Listening()
    with pytest.raises(NotConfigured):
        await listen_script(ask(golden_explainer(), "s2"), replace(listening.deps(), voices=()))


def test_listen_is_offered_in_the_languages_its_voices_read_named_by_the_first() -> None:
    listening = Listening()
    assert listen_offer(both(listening)).model_dump(mode="json", by_alias=True) == {
        "languages": EVERY_LANGUAGE,
        "voice": "ELEVENLABS",
    }
    assert listen_offer((listening.gemini(),)).model_dump(mode="json", by_alias=True) == {
        "languages": EVERY_LANGUAGE[:-1],
        "voice": "GEMINI",
    }
    assert listen_offer(()).model_dump(mode="json", by_alias=True) == {"languages": []}
