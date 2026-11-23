import hashlib
from datetime import UTC, datetime

import pytest

from app.core.errors import InvalidInput
from app.providers.elevenlabs import NARRATION_MAX_CHARACTERS, TimedSpeech
from app.research.explainer import Explainer
from app.services.naming import narration_file_name, narration_key
from app.voice.narration import (
    PART_CHARACTERS,
    NarrationPart,
    SpokenBlock,
    SpokenSentence,
    estimated_seconds,
    narration_cache_id,
    narration_parts,
    part_duration,
    part_words,
    spoken_blocks,
)

from ..contracts.golden import golden_json
from .listen_fakes import golden_explainer

HASH = "ae583a3bc299d098d3ec7b9e7faebf91a7f2f135d512a1218997b78d348e87f0"


def block(*sentences: tuple[str, str, str]) -> SpokenBlock:
    spoken = tuple(SpokenSentence(sentence_id=i, text=t, language=lang) for i, t, lang in sentences)
    return SpokenBlock(block_id="s9.b1", content_hash=HASH, sentences=spoken)


def even_speech(text: str, step: float) -> TimedSpeech:
    return TimedSpeech(
        audio=b"\xff" * 16,
        starts=tuple(index * step for index in range(len(text))),
        ends=tuple((index + 1) * step for index in range(len(text))),
    )


def test_listen_reads_the_cited_sentences_of_each_block_in_reading_order_and_skips_pictures() -> None:
    blocks = spoken_blocks(golden_explainer(), None)
    assert [b.block_id for b in blocks] == ["s1.b1", "s2.b1", "s3.b1"]
    assert [s.sentence_id for s in blocks[0].sentences] == [f"s1.b1.{n}" for n in range(1, 7)]
    assert blocks[1].content_hash == golden_json("explainer.piece.golden.json")["contentHash"]


def test_one_section_reads_only_its_own_blocks_and_an_unknown_section_reads_nothing() -> None:
    assert [b.block_id for b in spoken_blocks(golden_explainer(), "s2")] == ["s2.b1"]
    assert spoken_blocks(golden_explainer(), "s9") == []


def test_the_whole_answer_opens_with_its_lede_and_a_section_leaves_it_out() -> None:
    answered = Explainer.model_validate(golden_json("explainer.lede.golden.json"))
    whole = spoken_blocks(answered, None)
    assert [b.block_id for b in whole] == ["lede", "s1.b1", "s2.b1", "s3.b1"]
    assert [s.sentence_id for s in whole[0].sentences] == ["lede.1", "lede.2", "lede.3"]
    assert [b.block_id for b in spoken_blocks(answered, "s1")] == ["s1.b1"]


def test_a_hypothesis_outcome_is_not_read_aloud() -> None:
    [what_if] = spoken_blocks(what_if_explainer(hypothesis="s2.b1.2"), None)
    assert [s.sentence_id for s in what_if.sentences] == ["s2.b1.1", "s2.b1.3", "s2.b1.4"]


def test_the_cache_id_is_version_three_since_listen_sent_elevenlabs_no_square_brackets() -> None:
    parts = ("kalavigyan-narration", "3", "eleven_v4", "voice_1", "en", HASH)
    by_hand = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()
    assert narration_cache_id(HASH, language="en", voice_id="voice_1", model="eleven_v4") == by_hand


def what_if_explainer(*, hypothesis: str) -> Explainer:
    document = golden_json("explainer.document.golden.json")
    fixture = golden_json("explainer.phase-c.golden.json")
    block = fixture["sections"][1]["blocks"][0]
    for option in block["options"]:
        for outcome in option["outcomes"]:
            if outcome["sentence"]["id"] == hypothesis:
                outcome["sentence"]["level"] = "HYPOTHESIS"
                for citation in outcome["sentence"]["citations"]:
                    citation.update({"evidence": "INFERRED", "level": "HYPOTHESIS"})
    cited = [
        c["sourceId"] for o in block["options"] for x in o["outcomes"] for c in x["sentence"]["citations"]
    ]
    sources = {source["id"]: source for source in fixture["sources"]}
    section = {**document["sections"][1], "order": 1, "blocks": [block]}
    return golden_explainer(sections=[section], sources=[sources[sid] for sid in dict.fromkeys(cited)])


def test_listen_reads_a_sentence_once_where_the_page_says_it_and_not_again_under_a_table() -> None:
    document = golden_json("explainer.document.golden.json")
    fixture = golden_json("explainer.quantities.golden.json")
    section = {**document["sections"][1], "order": 1, "blocks": fixture["sections"][1]["blocks"]}
    explainer = golden_explainer(sections=[section], sources=fixture["sources"])
    spoken = spoken_blocks(explainer, None)
    assert [(b.block_id, [s.sentence_id for s in b.sentences]) for b in spoken] == [
        ("s2.b1", ["s2.b1.1"]),
        ("s2.b2", ["s2.b2.3", "s2.b2.4", "s2.b2.5"]),
    ]


def test_a_sentence_left_in_english_inside_a_hindi_explainer_is_spoken_in_english() -> None:
    document = golden_json("explainer.document.golden.json")
    first = document["sections"][1]["blocks"][0]["sentences"][0]
    first.update(
        {
            "text": "पानी में लोहा रंगों को फीका करता है।",
            "translated": True,
            "original": first["text"],
            "terms": [],
        }
    )
    explainer = golden_explainer(
        sections=document["sections"], understood={**document["understood"], "language": "hi"}
    )
    [water] = spoken_blocks(explainer, "s2")
    assert [s.language for s in water.sentences] == ["hi", "en", "en"]


def test_a_long_block_is_split_into_parts_within_the_provider_s_limit() -> None:
    sentences = [(f"s9.b1.{n}", ("x" * 599) + str(n), "en") for n in range(1, 6)]
    parts = narration_parts(block(*sentences))
    assert [len(part.text) for part in parts] == [1802, 1201]
    assert [len(part.sentences) for part in parts] == [3, 2]
    assert all(len(part.text) <= PART_CHARACTERS <= NARRATION_MAX_CHARACTERS for part in parts)


def test_a_change_of_language_starts_a_new_part() -> None:
    parts = narration_parts(
        block(("a", "One.", "en"), ("b", "Two.", "en"), ("c", "तीन।", "hi"), ("d", "Four.", "en"))
    )
    assert [(p.language, p.text) for p in parts] == [("en", "One. Two."), ("hi", "तीन।"), ("en", "Four.")]


def test_a_sentence_longer_than_a_part_is_refused() -> None:
    with pytest.raises(InvalidInput, match=r"s9\.b1\.1"):
        narration_parts(block(("s9.b1.1", "y" * (PART_CHARACTERS + 1), "en")))


def test_word_timings_align_to_the_shown_text_of_each_sentence() -> None:
    part = NarrationPart(
        language="en",
        sentences=(SpokenSentence("s.1", "Alum fixes.", "en"), SpokenSentence("s.2", "Iron darkens.", "en")),
    )
    words = part_words(part, even_speech(part.text, 0.1))
    assert [(w.sentence_id, w.text, w.start, w.end) for w in words] == [
        ("s.1", "Alum", 0.0, 0.4),
        ("s.1", "fixes.", 0.5, 1.1),
        ("s.2", "Iron", 1.2, 1.6),
        ("s.2", "darkens.", 1.7, 2.5),
    ]


def test_timings_that_step_back_are_held_in_reading_order() -> None:
    part = NarrationPart(language="en", sentences=(SpokenSentence("s.1", "a b c", "en"),))
    speech = TimedSpeech(audio=b"\xff", starts=(0.0, 0.3, 0.5, 0.4, 0.2), ends=(0.2, 0.4, 0.6, 0.5, 0.3))
    assert [(w.start, w.end) for w in part_words(part, speech)] == [(0.0, 0.2), (0.5, 0.6), (0.5, 0.5)]


def test_timings_for_other_text_are_refused() -> None:
    part = NarrationPart(language="en", sentences=(SpokenSentence("s.1", "Alum.", "en"),))
    with pytest.raises(InvalidInput):
        part_words(part, even_speech("Alum fixes.", 0.1))


def test_a_part_lasts_as_long_as_its_audio_or_its_last_word() -> None:
    assert part_duration(TimedSpeech(audio=b"\xff" * 32_000, starts=(0.0,), ends=(1.5,))) == 2.0
    assert part_duration(TimedSpeech(audio=b"\xff" * 16_000, starts=(0.0,), ends=(1.5,))) == 1.5


def test_the_cache_id_changes_with_the_content_the_language_and_the_voice() -> None:
    first = narration_cache_id(HASH, language="en", voice_id="voice_1", model="eleven_v4")
    gemini = narration_cache_id(HASH, language="en", voice_id="Kore", model="gemini-3.8-flash-tts")
    assert gemini != first and len(gemini) == 64
    assert first == narration_cache_id(HASH, language="en", voice_id="voice_1", model="eleven_v4")
    others = {
        narration_cache_id(HASH, language="hi", voice_id="voice_1", model="eleven_v4"),
        narration_cache_id(HASH, language="en", voice_id="voice_2", model="eleven_v4"),
        narration_cache_id("0" * 64, language="en", voice_id="voice_1", model="eleven_v4"),
    }
    assert first not in others and len(others) == 3 and len(first) == 64


def test_seconds_are_estimated_at_the_documented_thousand_characters_a_minute() -> None:
    assert [estimated_seconds(n) for n in (1, 1000, 1801, 10_000)] == [1, 60, 109, 600]


@pytest.mark.parametrize(
    "row", golden_json("naming-golden.json")["narrationFiles"], ids=lambda row: row["fileName"]
)
def test_narration_parts_are_named_by_the_one_convention(row: dict) -> None:
    moment = datetime.fromisoformat(row["generatedAt"])
    assert narration_file_name(moment, row["part"], ext=row.get("ext", "mp3")) == row["fileName"]
    key = narration_key(HASH, row["fileName"])
    assert key == f"media/narration/{HASH}/{row['fileName']}"


def test_a_narration_key_needs_a_cache_id_and_one_file_name() -> None:
    moment = datetime(2026, 11, 17, tzinfo=UTC)
    with pytest.raises(InvalidInput):
        narration_key("not-a-hash", narration_file_name(moment, 1))
    with pytest.raises(InvalidInput):
        narration_key(HASH, "nested/name.mp3")
    with pytest.raises(InvalidInput):
        narration_file_name(moment, 100)
