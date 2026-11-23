from datetime import date
from typing import Any

from app.data.interface_words import Review, WordEntry
from app.services.answer_events import stored_follow_ups
from app.services.explainer_events import ExplainerStream
from app.services.interface_words import InterfaceWords, essay_words, reviewed_of
from app.services.status_lines import status_message
from app.services.stored_explainer import shown_stored_heading

REVIEW = Review("A reader of Hindi", date(2026, 11, 30))
TRANSLATING = "Translating the answer into {language}"
TRANSLATING_HI = "उत्तर का {language} में अनुवाद हो रहा है"
HISTORY = "Where {craft} comes from"
HISTORY_HI = "{craft} कहाँ से आया"
CHEMISTRY_FOLLOW_UP = "What is the chemistry or physics behind {craft}?"
CHEMISTRY_FOLLOW_UP_HI = "{craft} के पीछे कौन सा रसायन या भौतिकी है?"


def entry(key: str, english: str, text: str, *, reviewed: bool = True) -> WordEntry:
    return WordEntry(key, english, text, "a test", REVIEW if reviewed else None)


def hindi(*entries: WordEntry) -> InterfaceWords:
    return reviewed_of("hi", entries)


def test_only_a_reviewed_word_is_shown() -> None:
    words = hindi(
        entry("stream.status", TRANSLATING, TRANSLATING_HI, reviewed=False),
        entry("stream.heading", HISTORY, HISTORY_HI),
    )
    assert words.shown("stream.status", TRANSLATING) is None
    assert words.shown("stream.heading", HISTORY) == HISTORY_HI


def test_a_word_whose_english_changed_since_its_review_is_not_shown() -> None:
    words = hindi(entry("stream.status", "Translating into {language}", TRANSLATING_HI))
    assert words.said("stream.status", TRANSLATING, language="Hindi") == "Translating the answer into Hindi"


def test_a_reviewed_status_line_names_the_language_by_its_own_name() -> None:
    words = hindi(entry("stream.status", TRANSLATING, TRANSLATING_HI))
    assert status_message("TRANSLATING", language="hi", words=words) == "उत्तर का हिन्दी में अनुवाद हो रहा है"
    assert status_message("TRANSLATING", language="hi") == "Translating the answer into Hindi"
    assert status_message("READING", 1) == "Reading the best of 1 source found"


async def test_the_stream_says_its_status_in_the_reviewed_words_of_its_language() -> None:
    sent: list[tuple[str, dict[str, Any]]] = []

    async def emit(event: str, data: dict[str, Any]) -> None:
        sent.append((event, data))

    stream = ExplainerStream(
        emit, language="hi", words=hindi(entry("stream.status", TRANSLATING, TRANSLATING_HI))
    )
    await stream.status("TRANSLATING")
    assert sent == [("status", {"step": "TRANSLATING", "message": "उत्तर का हिन्दी में अनुवाद हो रहा है"})]


def test_a_stored_heading_is_shown_in_its_reviewed_words_with_the_craft_named() -> None:
    words = hindi(entry("stream.heading", HISTORY, HISTORY_HI))
    assert shown_stored_heading("History", "Kutch Ajrakh", words) == "Kutch Ajrakh कहाँ से आया"
    assert shown_stored_heading("Design", "Kutch Ajrakh", words) == "The patterns of Kutch Ajrakh"
    long_name = "A" * 120
    assert shown_stored_heading("History", long_name, words) == "Where the craft comes from"


def test_a_stored_group_heading_is_shown_in_its_reviewed_words() -> None:
    words = hindi(entry("stream.heading", "The tradition", "परंपरा"))
    assert shown_stored_heading("The tradition", "Kutch Ajrakh", words) == "परंपरा"
    assert shown_stored_heading("Place and climate", "Kutch Ajrakh", words) == "Place and climate"


def test_a_stored_follow_up_is_asked_in_its_reviewed_words() -> None:
    words = hindi(entry("stream.followUp", CHEMISTRY_FOLLOW_UP, CHEMISTRY_FOLLOW_UP_HI))
    assert stored_follow_ups("Ajrakh", ["Materials and tools", "Process"], words) == [
        "Ajrakh के पीछे कौन सा रसायन या भौतिकी है?",
        "How do local water, soil and climate shape Ajrakh?",
        "How do artisans judge when a step of Ajrakh is done?",
    ]


def test_the_web_is_sent_only_the_reviewed_essay_words() -> None:
    assert essay_words("en") == []
    assert all(word["key"].startswith("essay.") for word in essay_words("ur"))
