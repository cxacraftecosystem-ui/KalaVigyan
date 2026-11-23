from app.research.translation_meaning import ADDED_HEDGE, ADDED_NEGATION, meaning_problems

ALUM = "Alum fixes the madder red on cotton before the indigo vat."


def test_a_reading_that_says_what_the_english_says_passes() -> None:
    assert meaning_problems(ALUM, "Alum fixes madder red onto cotton before the indigo vat.") == []


def test_a_reading_in_other_words_passes_while_it_keeps_half_the_english_terms() -> None:
    reading = "Alum binds the madder colour to the cotton ahead of the indigo bath."
    assert meaning_problems(ALUM, reading) == []


def test_a_reading_about_something_else_is_refused_naming_the_terms_it_lost() -> None:
    reading = "Iron darkens the cloth after the blue dye bath."
    assert meaning_problems(ALUM, reading) == [
        "it keeps 0 of the English's 5 terms; lost: alum, cott, fixe, indi, madd"
    ]


def test_a_reading_that_adds_a_negation_is_refused() -> None:
    english = "Alum fixes the madder red on cotton."
    assert meaning_problems(english, "Alum does not fix the madder red on cotton.") == [ADDED_NEGATION]


def test_a_reading_that_drops_the_negation_is_refused() -> None:
    english = "Lime does not hold the alum."
    assert meaning_problems(english, "Lime holds the alum.") == [
        "the original's negation (not, no, never, without) is missing"
    ]


def test_a_reading_with_another_figure_is_refused() -> None:
    english = "The bath is heated to 60 °C."
    assert meaning_problems(english, "The bath is heated to 65 °C.") == [
        "number 60 is missing",
        "number 65 is not in the original",
    ]


def test_a_reading_that_adds_a_hedge_is_refused() -> None:
    english = "Alum fixes the red on cotton."
    assert meaning_problems(english, "Alum may fix the red on cotton.") == [ADDED_HEDGE]


def test_a_reading_that_drops_the_hedge_is_refused() -> None:
    english = "Alum may fix the red on cotton."
    assert meaning_problems(english, "Alum fixes the red on cotton.") == [
        "the original's hedge (may) is missing"
    ]


def test_a_reading_left_in_another_script_is_refused() -> None:
    problems = meaning_problems(ALUM, "फिटकरी नील के कुंड से पहले कपास पर मजीठ का लाल पक्का करती है।")
    assert "the translation is not written in the Latn script" in problems


def test_a_text_too_short_to_count_its_terms_is_held_only_to_its_figures_and_stance() -> None:
    assert meaning_problems("Mordant", "Colour fixer") == []
    assert meaning_problems("Heated to 60 °C", "Warmed to 60 °C") == []
