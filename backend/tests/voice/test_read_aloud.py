import pytest

from app.core.errors import ExternalFailure
from app.voice.audio import wav_seconds
from app.voice.narration import NarrationPart, SpokenSentence
from app.voice.read_aloud import Pcm, sentence_timed, wav_frames

from .listen_fakes import SPEECH_RATE, spoken_wav

PART = NarrationPart(
    language="en",
    sentences=(
        SpokenSentence(sentence_id="s2.b1.1", text="Alum fixes the red.", language="en"),
        SpokenSentence(sentence_id="s2.b1.2", text="Iron darkens it.", language="en"),
    ),
)


def silence(frames: int, rate: int = SPEECH_RATE) -> Pcm:
    return Pcm(frames=bytes(frames * 2), rate=rate)


def test_each_sentence_is_timed_from_the_samples_read_before_it() -> None:
    timed = sentence_timed(PART, [silence(2_400), silence(36_000)])
    assert [(s.sentence_id, s.start, s.end) for s in timed.sentences] == [
        ("s2.b1.1", 0.0, 0.1),
        ("s2.b1.2", 0.1, 1.6),
    ]
    assert (timed.duration_seconds, timed.billed_seconds) == (1.6, 2)
    assert wav_seconds(timed.audio) == 1.6
    joined = wav_frames(timed.audio)
    assert (joined.rate, len(joined.frames)) == (SPEECH_RATE, 76_800)


def test_a_part_read_at_two_rates_or_missing_a_sentence_is_refused() -> None:
    with pytest.raises(ExternalFailure, match="different sample rates"):
        sentence_timed(PART, [silence(2_400), silence(2_400, rate=16_000)])
    with pytest.raises(ExternalFailure, match="not each once"):
        sentence_timed(PART, [silence(2_400)])


def test_only_mono_sixteen_bit_speech_is_read() -> None:
    read = wav_frames(spoken_wav("Alum fixes the red."))
    assert (read.rate, read.count) == (SPEECH_RATE, 22_800)
    for refused in (spoken_wav("Alum", channels=2), spoken_wav("Alum", width=1), b"ID3 not a wav"):
        with pytest.raises(ExternalFailure) as failure:
            wav_frames(refused)
        assert failure.value.service == "gemini"
