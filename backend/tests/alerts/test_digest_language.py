from collections.abc import Mapping

from app.research.alerts import WeeklyDigest
from app.services.alert_digest import DIGEST_OPENING, DIGEST_STOP, DIGEST_SUBJECT, digest_mail, digest_texts
from app.services.answer_translation import AnswerTranslation
from app.services.digest_language import DigestTranslations, digest_language

from ..contracts.learning_golden import ALERTS, AlertsFixture, learning
from .digest_words import HINDI, NEWS, KnownTranslator, NoCache

WEB = "https://kalavigyan.example.org"


def golden_digest() -> WeeklyDigest:
    return AlertsFixture.model_validate(learning(ALERTS)).digest


def translations(known: Mapping[str, str]) -> tuple[DigestTranslations, KnownTranslator]:
    translator = KnownTranslator(known)
    return DigestTranslations(AnswerTranslation(translator=translator, cache=NoCache())), translator


def test_the_digest_s_fixed_lines_are_its_subject_opening_news_and_settings_line() -> None:
    assert digest_texts(golden_digest()) == [DIGEST_SUBJECT, DIGEST_OPENING, NEWS, DIGEST_STOP]


def test_a_rendered_digest_is_written_in_the_reader_s_language_around_its_own_words() -> None:
    mail = digest_mail("reader@example.org", golden_digest(), web_url=WEB, rendered=HINDI)
    assert mail.subject == "आपके सहेजे गए KalaVigyan व्याख्यान बेहतर हुए"
    assert mail.text.splitlines() == [
        "आपके सहेजे गए व्याख्यानों के लिए इस सप्ताह नए उद्धृत निष्कर्ष आए।",
        "",
        "How is Kutch Ajrakh made, and why does its water matter?",
        "Kutch Ajrakh: 4 नए निष्कर्ष (भूगोल और जल में 3, इतिहास में 1)",
        f"{WEB}/ask?explainer=0c5e7a1d-2b3f-4c6d-8e9f-a0b1c2d3e4f5",
        "",
        f"सेटिंग्स में ये ईमेल बंद करें: {WEB}/settings",
    ]


def test_a_line_with_no_rendering_stays_in_english() -> None:
    mail = digest_mail("reader@example.org", golden_digest(), web_url=WEB, rendered={NEWS: HINDI[NEWS]})
    lines = mail.text.splitlines()
    assert mail.subject == DIGEST_SUBJECT
    assert (lines[0], lines[-1]) == (DIGEST_OPENING, f"{DIGEST_STOP} {WEB}/settings")
    assert lines[3] == "Kutch Ajrakh: 4 नए निष्कर्ष (भूगोल और जल में 3, इतिहास में 1)"


async def test_fixed_lines_are_translated_once_per_language_in_a_run() -> None:
    words, translator = translations(HINDI)
    texts = digest_texts(golden_digest())
    first = await words.rendered("hi", texts)
    again = await words.rendered("hi", texts)
    assert first == again == HINDI
    assert translator.asked == [
        [
            ("digest:0", DIGEST_SUBJECT),
            ("digest:1", DIGEST_OPENING),
            ("digest:2", NEWS),
            ("digest:3", DIGEST_STOP),
        ]
    ]


async def test_english_readers_and_a_run_without_a_translator_ask_for_nothing() -> None:
    words, translator = translations(HINDI)
    assert await words.rendered("en", digest_texts(golden_digest())) == {}
    assert translator.asked == []
    assert await DigestTranslations(None).rendered("hi", digest_texts(golden_digest())) == {}


async def test_a_line_the_translator_does_not_return_is_asked_again_for_the_next_reader() -> None:
    words, translator = translations({DIGEST_SUBJECT: HINDI[DIGEST_SUBJECT]})
    assert await words.rendered("hi", [DIGEST_SUBJECT, DIGEST_STOP]) == {
        DIGEST_SUBJECT: HINDI[DIGEST_SUBJECT]
    }
    await words.rendered("hi", [DIGEST_SUBJECT, DIGEST_STOP])
    assert translator.asked[1] == [("digest:0", DIGEST_STOP)]


def test_a_reader_with_no_chosen_language_reads_english() -> None:
    assert [digest_language(value) for value in ("auto", None, "hi", "ta")] == ["en", "en", "hi", "ta"]
