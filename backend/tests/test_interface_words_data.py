from datetime import date
from typing import Any

import pytest

from app.data.interface_words import Review, load_interface_words, parse_interface_words, placeholders_of
from app.research.sections import FALLBACK_HEADINGS
from app.research.translation import written_in
from app.research.vocabulary import ANSWER_LANGUAGE_SPECS
from app.services.answer_events import STORED_FOLLOW_UP_QUESTIONS
from app.services.status_lines import COUNTED_LINES, PLAIN_LINES, PLANNING, PLANNING_ON
from app.services.stored_explainer import HEADING_DISCIPLINES
from app.voice import phrases

SAVE = {"key": "essay.actions", "english": "Save", "text": "محفوظ کریں", "source": "the board"}


def words(*entries: dict[str, Any], language: str = "ur") -> dict[str, Any]:
    return {"schemaVersion": 1, "language": language, "words": list(entries)}


def test_an_entry_is_read_with_its_source_and_its_review() -> None:
    reviewed = {**SAVE, "review": {"by": "A reader of Urdu", "on": "2026-11-30"}}
    first, second = parse_interface_words(
        words({**SAVE, "review": None}, {**reviewed, "english": "Saved"}), "ur"
    )
    assert (first.key, first.english, first.text, first.source, first.review) == (
        "essay.actions",
        "Save",
        "محفوظ کریں",
        "the board",
        None,
    )
    assert second.review == Review("A reader of Urdu", date(2026, 11, 30))


@pytest.mark.parametrize(
    ("raw", "message"),
    [
        ({**words(), "schemaVersion": 2}, "schemaVersion 1"),
        (words(language="hi"), "names 'hi'"),
        (words({**SAVE, "review": None}, {**SAVE, "review": None}), "gives 'Save' twice"),
        (words({**SAVE, "english": "Drawn from {count} sources", "review": None}), "same placeholders"),
        (words({**SAVE, "key": "Save", "review": None}), "dotted interface word key"),
        (words({**SAVE, "source": " ", "review": None}), "non-empty source"),
        (words({**SAVE, "review": {"by": "A reader"}}), "a review names who read it"),
        (words({**SAVE, "review": {"by": "A reader", "on": "30 November"}}), "YYYY-MM-DD"),
        (words({**SAVE, "review": {"by": " ", "on": "2026-11-30"}}), "names its reader"),
    ],
)
def test_a_malformed_words_file_is_refused_naming_what_is_wrong(raw: dict[str, Any], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        parse_interface_words(raw, "ur")


def test_placeholders_are_read_in_order_of_their_names() -> None:
    assert placeholders_of("{count} ماخذوں سے") == ["count"]
    assert placeholders_of("Planning the research on {craft} in {language}") == ["craft", "language"]


def test_every_word_is_written_in_the_script_of_its_language() -> None:
    for language, entries in load_interface_words().items():
        script = ANSWER_LANGUAGE_SPECS[language].script
        for entry in entries:
            bare = entry.text
            for name in placeholders_of(bare):
                bare = bare.replace(f"{{{name}}}", "")
            assert written_in(bare, script), (language, entry.key, entry.text)


def test_every_stream_and_voice_word_translates_an_english_text_the_backend_shows() -> None:
    stream = {
        "stream.status": {
            PLANNING,
            PLANNING_ON,
            *PLAIN_LINES.values(),
            *(t for p in COUNTED_LINES.values() for t in p),
        },
        "stream.heading": {*FALLBACK_HEADINGS.values(), *HEADING_DISCIPLINES},
        "stream.followUp": set(STORED_FOLLOW_UP_QUESTIONS.values()),
    }
    spoken = {table["en"] for table in phrases.PHRASE_TABLES} | set(phrases.SOURCE_WORDS["en"])
    for language, entries in load_interface_words().items():
        for entry in entries:
            if entry.key.startswith("stream."):
                assert entry.english in stream[entry.key], (language, entry.key, entry.english)
            if entry.key.startswith("voice."):
                assert entry.english in spoken, (language, entry.key, entry.english)
