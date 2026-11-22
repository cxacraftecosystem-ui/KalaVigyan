from decimal import Decimal

import pytest
from pint.errors import DimensionalityError

from app.research.local_units import LOCAL_UNITS
from app.research.measures import DEFINED_UNITS
from app.research.stated_quantities import UNIT_WORDS, stated_factors, stated_quantities
from app.research.unit_registry import PINT_NAMES, measures_alike, metric_unit_named, unit_registry

from ..contracts.phase_d_golden import phase_d_blocks

PINT_DEFINED_NAMES = {
    "inch": "inch",
    "foot": "foot",
    "yard": "yard",
    "mile": "mile",
    "square-foot": "foot ** 2",
}


def read(text: str) -> list[tuple[str, Decimal, Decimal | None, str, str]]:
    return [(q.stated, q.low, q.high, q.unit_label, q.unit) for q in stated_quantities(text)]


def test_the_fixture_s_sentence_states_ten_to_fifteen_feet() -> None:
    row = phase_d_blocks()["s4.b1"]["rows"][0]
    assert read(row["sentence"]["text"]) == [("10-15 feet", Decimal(10), Decimal(15), "feet", "foot")]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        (
            "Pieces range in size from 1 inch to 14 feet.",
            [("1 inch", Decimal(1), None, "inch", "inch"), ("14 feet", Decimal(14), None, "feet", "foot")],
        ),
        (
            "The pit is about one foot deep and 2 to 2.5 feet across.",
            [("2 to 2.5 feet", Decimal(2), Decimal("2.5"), "feet", "foot")],
        ),
        ("It soaks the cloth and pounds it with the feet.", []),
        ("A 6-foot loom", [("6-foot", Decimal(6), None, "foot", "foot")]),
        ("A shed of 1,500 sq. ft.", [("1,500 sq. ft.", Decimal(1500), None, "sq. ft.", "square-foot")]),
        (
            "Add 5 seers of alum and 2 tolas of indigo.",
            [("5 seers", Decimal(5), None, "seers", "seer"), ("2 tolas", Decimal(2), None, "tolas", "tola")],
        ),
        ("A piece was valued at Rs. 7 in 1975.", []),
        ("Water fell by 15-10 feet.", []),
        ("At 200 feet, then 200 feet again.", [("200 feet", Decimal(200), None, "feet", "foot")]),
    ],
)
def test_a_quantity_is_a_number_with_a_unit_word_after_it(text: str, expected: list[object]) -> None:
    assert read(text) == expected


def test_every_unit_word_names_one_defined_or_local_unit() -> None:
    assert set(UNIT_WORDS.values()) == set(DEFINED_UNITS) | set(LOCAL_UNITS)
    assert not set(DEFINED_UNITS) & set(LOCAL_UNITS)


def test_the_defined_factors_follow_from_the_inch_of_2_54_cm() -> None:
    inch_in_m = Decimal("0.0254")
    foot = inch_in_m * 12
    assert DEFINED_UNITS["inch"].factor == inch_in_m * 100
    assert DEFINED_UNITS["foot"].factor == foot
    assert DEFINED_UNITS["yard"].factor == foot * 3
    assert DEFINED_UNITS["mile"].factor == foot * 5280 / 1000
    assert DEFINED_UNITS["square-foot"].factor == foot * foot


def test_pint_s_own_definitions_agree_with_the_defined_factors() -> None:
    plain = unit_registry()
    for key, unit in DEFINED_UNITS.items():
        target = PINT_NAMES[unit.metric_unit]
        converted = plain.Quantity(1, PINT_DEFINED_NAMES[key]).to(target).magnitude
        assert converted == pytest.approx(float(unit.factor), rel=1e-12)


@pytest.mark.parametrize("unit", sorted(LOCAL_UNITS))
def test_pint_knows_each_local_unit_and_never_converts_it_by_itself(unit: str) -> None:
    registry = unit_registry()
    assert str(registry.parse_units(f"{unit}s")) == unit
    with pytest.raises(DimensionalityError):
        registry.Quantity(1, unit).to(PINT_NAMES[LOCAL_UNITS[unit].measures])


@pytest.mark.parametrize(
    ("word", "unit"),
    [
        ("kilograms", "kg"),
        ("kg.", "kg"),
        ("kilos", "kg"),
        ("grams", "g"),
        ("gms", "g"),
        ("sq m", "m2"),
        ("square metres", "m2"),
        ("hectares", "ha"),
        ("litres", "l"),
        ("metres", "m"),
        ("acres", None),
        ("tolas", None),
        ("feet", None),
        ("rupees", None),
        ("seconds", None),
    ],
)
def test_pint_reads_the_metric_unit_a_source_states(word: str, unit: str | None) -> None:
    assert metric_unit_named(word) == unit


def test_a_local_unit_converts_only_to_a_metric_unit_of_its_own_quantity() -> None:
    assert measures_alike("seer", "kg") and measures_alike("tola", "kg") and measures_alike("bigha", "ha")
    assert not measures_alike("tola", "m") and not measures_alike("gaj", "m2")
    assert not measures_alike("foot", "m")


@pytest.mark.parametrize(
    ("quote", "expected"),
    [
        ("A seer of Kutch weighs 0.933 kg.", [("seer", Decimal("0.933"), "kg")]),
        ("One maund was equal to 37.32 kilograms in Gujarat.", [("maund", Decimal("37.32"), "kg")]),
        ("Here 933 grams make a seer.", [("seer", Decimal(933), "g")]),
        ("One bigha is about 1,618 sq m.", [("bigha", Decimal(1618), "m2")]),
        ("1 seer = 80 tolas.", []),
        ("One maund of cotton yields 12 kg of thread.", []),
        ("A tola weighs 11.66 metres.", []),
        ("A seer of indigo cost 2 rupees.", []),
        ("A foot is 0.3048 m.", []),
    ],
)
def test_a_regional_factor_is_only_a_stated_equality_with_a_metric_unit(
    quote: str, expected: list[tuple[str, Decimal, str]]
) -> None:
    assert [(f.unit, f.factor, f.metric_unit) for f in stated_factors(quote)] == expected
