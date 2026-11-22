import pytest

from app.research.quotes import unsupported_figures
from app.research.stated_figures import element_formulas_in


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


def test_a_quantity_that_converts_to_another_value_is_not_supported() -> None:
    assert unsupported_figures("Heat it to 61 °C.", ["heated to 140 °F"]) == ["61"]
    assert unsupported_figures("The river is 3 km away.", ["2000 m from the village"]) == ["3"]


def test_element_only_formulas_are_figures_but_acronyms_are_not() -> None:
    assert unsupported_figures("Salt is NaCl.", ["common salt, NaCl, is added"]) == []
    assert unsupported_figures("Salt is NaCl.", ["common salt is added"]) == ["NaCl"]
    assert unsupported_figures("The WHO and the NHS agree.", []) == []
    assert element_formulas_in("CuO and FeO but not Indigo or WHO") == ["CuO", "FeO"]
