import json
from pathlib import Path
from typing import Any

import httpx

from app.providers.elevenlabs import ElevenLabs, TimedSpeech
from app.scripts.paid_check_steps import NARRATIONS
from app.voice.listen_voices import ElevenLabsVoice, untagged
from app.voice.narration import CHARACTERS_PER_MINUTE, NarrationPart, SpokenSentence

from .listen_fakes import Narrations

FIXTURES = Path(__file__).parent / "fixtures"
REPLIES = {"en": "narration_with_timestamps.json", "hi": "narration_with_timestamps_hi.json"}


def fixture(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


async def heard(language: str) -> TimedSpeech:
    reply = fixture(REPLIES[language])
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, json=reply)))
    eleven = ElevenLabs(api_key="test-only-elevenlabs-key", client=client)
    return await eleven.narration(NARRATIONS[language], voice_id="voice_1", language=language)


def bracketed_seconds(speech: TimedSpeech, text: str) -> float:
    return round(speech.ends[text.index("]")] - speech.starts[text.index("[")], 3)


async def test_eleven_v4_times_both_recorded_narrations_code_point_for_code_point() -> None:
    english, hindi = await heard("en"), await heard("hi")
    assert (len(english.starts), english.ends[-1]) == (101, 6.88)
    assert (len(hindi.starts), hindi.ends[-1]) == (103, 8.08)


def test_the_recorded_speech_is_slower_than_the_hold_assumes() -> None:
    checks = fixture("paid_checks_report.json")["checks"]
    rates = {language: checks[f"narration_{language}"]["charactersPerMinute"] for language in REPLIES}
    assert rates == {"en": 882, "hi": 765}
    for language, rate in rates.items():
        found = checks[f"narration_{language}"]
        assert (found["model"], found["alignmentSpellsTheText"]) == ("eleven_v4", True)
        assert round(found["characters"] * 60 / found["audioSeconds"]) == rate
    assert max(rates.values()) < CHARACTERS_PER_MINUTE


async def test_v4_spoke_the_english_bracketed_words_and_skipped_the_hindi_ones() -> None:
    assert bracketed_seconds(await heard("en"), NARRATIONS["en"]) == 1.44
    assert bracketed_seconds(await heard("hi"), NARRATIONS["hi"]) == 0.075


async def test_listen_sends_elevenlabs_no_square_brackets_and_keeps_the_shown_words() -> None:
    shown = "Ajrakh is printed [in several stages] and washed."
    part = NarrationPart(language="en", sentences=(SpokenSentence("s1.b1.1", shown, "en"),))
    narrator = Narrations()
    spoken = await ElevenLabsVoice(narrator=narrator, voice_id="voice_1").spoken([part], 0)
    assert narrator.calls[0]["text"] == "Ajrakh is printed (in several stages) and washed."
    assert [word.text for word in spoken.words][3:6] == ["[in", "several", "stages]"]
    assert untagged("[a] [b]") == "(a) (b)"
