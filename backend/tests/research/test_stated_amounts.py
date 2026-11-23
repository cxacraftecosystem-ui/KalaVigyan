from decimal import Decimal

import pytest

from app.research.stated_amounts import stated_amounts


def read(text: str) -> list[tuple[str, Decimal, Decimal | None, str, str]]:
    return [(a.stated, a.low, a.high, a.unit, a.measures) for a in stated_amounts(text)]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "The kiln reaches 450–600 °C and the vat is held at pH 11 for 10-minute dips.",
            [
                ("450–600 °C", Decimal(450), Decimal(600), "degree-celsius", "TEMPERATURE"),
                ("pH 11", Decimal(11), None, "ph", "ACIDITY"),
                ("10-minute", Decimal(10), None, "minute", "TIME"),
            ],
        ),
        (
            "Annual rainfall is 556 mm, and temperatures range from 3 to 50 degrees Celsius.",
            [
                ("556 mm", Decimal(556), None, "millimetre", "LENGTH"),
                ("3 to 50 degrees Celsius", Decimal(3), Decimal(50), "degree-celsius", "TEMPERATURE"),
            ],
        ),
        (
            "Pastes above 0.5% are pseudoplastic; 8 g/L of alum and 2 seers of madder go in.",
            [
                ("0.5%", Decimal("0.5"), None, "percent", "SHARE"),
                ("8 g/L", Decimal(8), None, "gram-per-litre", "CONCENTRATION"),
                ("2 seers", Decimal(2), None, "seer", "MASS"),
            ],
        ),
        (
            "The cloth is 2.5 m long, 1 M wide and lasts 5-6 times a day.",
            [("2.5 m", Decimal("2.5"), None, "metre", "LENGTH")],
        ),
    ],
)
def test_an_amount_is_a_number_with_a_unit_as_written(text: str, expected: list[object]) -> None:
    assert read(text) == expected


def test_years_prices_counts_feet_and_cubed_units_are_not_amounts() -> None:
    assert read("In 1975 a piece cost Rs. 7; 40 families dug 200 feet and made 1-2 m³ of effluent.") == []


def test_the_same_words_twice_in_one_text_are_one_amount() -> None:
    assert [a.stated for a in stated_amounts("At 573 °C quartz changes; passing 573 °C cracks ware.")] == [
        "573 °C"
    ]
