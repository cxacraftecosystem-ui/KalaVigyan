from app.data.interface_words import load_interface_words
from app.research.stance_markers import negation_marked
from app.research.vocabulary import ANSWER_LANGUAGES
from app.voice.languages import VOICE_LANGUAGES
from app.voice.phrases import (
    NO_EVIDENCE_REPLIES,
    PHRASE_TABLES,
    SOURCE_WORDS,
    UNSAID_REPLIES,
    phrased_languages,
)

NEGATED_ENGLISH = (
    "I found no cited answer to that about {craft} yet.",
    "I could not prepare that answer just now. Please ask again.",
)


def test_the_english_phrases_that_say_no_are_the_two_the_checker_reads_as_negated() -> None:
    assert (
        tuple(table["en"] for table in PHRASE_TABLES if negation_marked(table["en"], "en")) == NEGATED_ENGLISH
    )
    assert (NO_EVIDENCE_REPLIES["en"], UNSAID_REPLIES["en"]) == NEGATED_ENGLISH


def test_every_phrase_says_no_in_every_offered_language_exactly_where_its_english_does() -> None:
    for table in PHRASE_TABLES:
        negated = negation_marked(table["en"], "en")
        for language in VOICE_LANGUAGES:
            assert negation_marked(table[language], language) == negated, (language, table[language])


def test_a_bengali_pronoun_ending_like_a_negative_is_not_read_as_one() -> None:
    assert not negation_marked("আপনি কোন শিল্পের কথা বলছেন?", "bn")
    assert not negation_marked("তিনি কাপড়ে ছাপ দেন।", "bn")
    assert negation_marked("তিনি কাপড়ে ছাপ দেননি।", "bn")


def test_a_fused_negative_is_read_as_a_negation_and_its_positive_is_not() -> None:
    assert negation_marked("ଉତ୍ତର ମିଳିନାହିଁ।", "or")
    assert not negation_marked("ଉତ୍ତର ମିଳିଲା।", "or")
    assert negation_marked("ఈ సమాధానం సిద్ధం చేయలేకపోయాను.", "te")
    assert not negation_marked("ఈ సమాధానం సిద్ధం చేశాను.", "te")
    assert negation_marked("উত্তৰ প্ৰস্তুত কৰিব পৰা নগ'ল।", "as")
    assert not negation_marked("উত্তৰ প্ৰস্তুত হ'ল।", "as")


def test_every_answer_language_other_than_english_keeps_its_spoken_phrases_in_its_words_file() -> None:
    files = load_interface_words()
    assert sorted(files) == sorted(language for language in ANSWER_LANGUAGES if language != "en")
    for language, entries in files.items():
        spoken = [entry for entry in entries if entry.key.startswith("voice.")]
        assert len(spoken) == 8, language
        assert all(entry.review is None for entry in spoken), language


def test_voice_offers_only_a_language_whose_every_phrase_is_written() -> None:
    assert phrased_languages(("en", "hi", "xx")) == ("en", "hi")
    assert all(language in SOURCE_WORDS for language in VOICE_LANGUAGES)
