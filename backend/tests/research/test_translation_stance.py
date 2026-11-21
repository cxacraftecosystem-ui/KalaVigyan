from app.research.stance_markers import HEDGE_MARKERS, NEGATION_MARKERS
from app.research.translation import translation_problems
from app.research.vocabulary import ANSWER_LANGUAGES, CANONICAL_LANGUAGE

NEGATION_MISSING = "the original's negation (not, no, never, without) is missing"


def test_a_translation_that_drops_the_original_s_negation_is_refused() -> None:
    english = "Alum is not used in Bagru."
    assert translation_problems(english, "बगरू में फिटकरी का प्रयोग होता है।", language="hi") == [NEGATION_MISSING]
    assert translation_problems(english, "बगरू में फिटकरी का प्रयोग नहीं होता है।", language="hi") == []


def test_a_negation_written_as_a_verb_ending_counts() -> None:
    english = "Alum is not used."
    assert translation_problems(english, "படிகாரம் பயன்படுத்தப்படுவதில்லை.", language="ta") == []
    assert translation_problems(english, "படிகாரம் பயன்படுத்தப்படுகிறது.", language="ta") == [NEGATION_MISSING]


def test_a_translation_that_drops_the_original_s_hedge_is_refused() -> None:
    english = "The red may come from iron."
    assert translation_problems(english, "लाल रंग लोहे से आता है।", language="hi") == [
        "the original's hedge (may) is missing"
    ]
    assert translation_problems(english, "लाल रंग लोहे से आ सकता है।", language="hi") == []


def test_an_approximate_figure_keeps_its_approximation() -> None:
    english = "Some 400 printers work in the village."
    assert translation_problems(english, "गाँव में 400 छपाईकार काम करते हैं।", language="hi") == [
        "the original's hedge (some) is missing"
    ]
    assert translation_problems(english, "गाँव में लगभग 400 छपाईकार काम करते हैं।", language="hi") == []


def test_every_translated_language_has_its_negation_and_hedge_words() -> None:
    translated = set(ANSWER_LANGUAGES) - {CANONICAL_LANGUAGE}
    assert set(NEGATION_MARKERS) == translated
    assert set(HEDGE_MARKERS) == translated
