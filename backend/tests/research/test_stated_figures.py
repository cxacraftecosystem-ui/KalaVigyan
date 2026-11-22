import pytest

from app.research.quotes import unsupported_figures
from app.research.stated_figures import element_formulas_in, number_words_in


@pytest.mark.parametrize(
    ("sentence", "quote"),
    [
        ("Heat the bath to 60 °C.", "the bath was heated to 140 °F"),
        ("The river is 2 km from the village.", "the river runs 2000 m from the village"),
        ("Soak it for 2 days.", "soaked for 48 hours"),
        ("Mordant baths held 8 g/L alum.", "baths of 8 g/l alum"),
        ("Water boils at 100 °C.", "water boils at 100 degrees"),
    ],
)
def test_a_quantity_is_supported_by_the_same_measure_in_any_unit(sentence: str, quote: str) -> None:
    assert unsupported_figures(sentence, [quote]) == []


def test_a_quantity_is_not_supported_by_the_same_number_of_another_measure() -> None:
    assert unsupported_figures("Add 60 g of alum.", ["the bath is kept at 60 °C"]) == ["60"]
    assert unsupported_figures("Heat it to 61 °C.", ["heated to 140 °F"]) == ["61"]


@pytest.mark.parametrize(
    ("sentence", "quote", "missing"),
    [
        ("Three dyes are used.", "the 3 dyes of the cloth", []),
        ("3 dyes are used.", "three dyes are used", []),
        ("Three dyes are used.", "four dyes are used", ["3"]),
        ("It is washed twenty-five times.", "washed 25 times", []),
        ("Three hundred printers work here.", "some 300 printers", []),
        ("A dozen blocks are carved.", "12 blocks", []),
        ("One of the oldest crafts.", "an old craft", []),
    ],
)
def test_number_words_are_figures_on_both_sides(sentence: str, quote: str, missing: list[str]) -> None:
    assert unsupported_figures(sentence, [quote]) == missing


def test_element_only_formulas_are_figures_but_acronyms_are_not() -> None:
    assert unsupported_figures("Salt is NaCl.", ["common salt, NaCl, is added"]) == []
    assert unsupported_figures("Salt is NaCl.", ["common salt is added"]) == ["NaCl"]
    assert unsupported_figures("The WHO and the NHS agree.", []) == []
    assert element_formulas_in("CuO and FeO but not Indigo or WHO") == ["CuO", "FeO"]


def test_number_words_read_as_values() -> None:
    assert number_words_in("Seventeen blocks, seventy dyers and three thousand metres") == [
        "17",
        "70",
        "3000",
    ]
