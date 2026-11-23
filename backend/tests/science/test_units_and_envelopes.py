import math

import pytest

from app.core.errors import InvalidInput
from app.science.envelopes import PHYSICAL_CONSTANTS, STAGE_ENVELOPES, envelope_check, envelope_for
from app.science.units import Bounds, normalised_bounds
from app.services.science_seed import load_science_seed

from ..contracts.golden import plan_text


@pytest.mark.parametrize(
    ("quantity", "stated", "unit", "expected"),
    [
        ("DURATION", (10, 15), "day", (240.0, 360.0)),
        ("DURATION", (2, 2), "week", (336.0, 336.0)),
        ("DURATION", (None, 4), "hour", (None, 4.0)),
        ("DURATION", (3, None), "day", (72.0, None)),
        ("DURATION", (30, 45), "minute", (0.5, 0.75)),
        ("DURATION", (1.5, 1.5), "hour", (1.5, 1.5)),
        ("TEMPERATURE", (212, 212), "degF", (100.0, 100.0)),
        ("TEMPERATURE", (373.15, 373.15), "K", (100.0, 100.0)),
        ("TEMPERATURE", (60, 90), "°C", (60.0, 90.0)),
        ("CONCENTRATION", (80, 100), "g/L", (80.0, 100.0)),
        ("CONCENTRATION", (5, 5), "mg/mL", (5.0, 5.0)),
        ("PRESSURE", (1, 1), "atm", (101.325, 101.325)),
        ("PH", (4.0, 4.8), "pH", (4.0, 4.8)),
    ],
)
def test_readings_are_normalised_to_one_unit_per_quantity(
    quantity: str, stated: tuple[float | None, float | None], unit: str, expected: tuple[float | None, ...]
) -> None:
    bounds = normalised_bounds(quantity, Bounds(*stated), unit)
    assert (bounds.low, bounds.high) == expected


@pytest.mark.parametrize(
    ("quantity", "stated", "unit"),
    [
        ("DURATION", (1, 2), "metre"),
        ("DURATION", (1, 2), "fortnights of fog"),
        ("TEMPERATURE", (1, 2), "hour"),
        ("PH", (4, 5), "degC"),
        ("DURATION", (None, None), "hour"),
        ("DURATION", (5, 2), "hour"),
        ("DURATION", (math.inf, None), "hour"),
        ("COLOUR", (1, 2), "hour"),
    ],
)
def test_a_reading_that_cannot_be_normalised_is_refused(
    quantity: str, stated: tuple[float | None, float | None], unit: str
) -> None:
    with pytest.raises(InvalidInput):
        normalised_bounds(quantity, Bounds(*stated), unit)


def test_the_envelopes_are_plan_seven() -> None:
    bounds = {key: (e.min, e.max) for key, e in STAGE_ENVELOPES.items()}
    assert bounds == {
        ("DYE", "TEMPERATURE"): (20.0, 100.0),
        ("DYE", "PH"): (2.0, 12.0),
        ("MORDANT", "TEMPERATURE"): (15.0, 100.0),
        ("FIRE", "TEMPERATURE"): (500.0, 1300.0),
        ("CAST", "TEMPERATURE"): (700.0, 1200.0),
    }
    section = plan_text().split("## 7. Science engine", 1)[1].split("\n## ", 1)[0]
    for phrase in ("DYE 20–100 °C, pH 2–12", "FIRE 500–1300 °C", "CAST 700–1200 °C", "MORDANT 15–100 °C"):
        assert phrase in section


@pytest.mark.parametrize(
    ("stage_type", "quantity", "low", "high", "status"),
    [
        ("DYE", "TEMPERATURE", 60.0, 80.0, "WITHIN"),
        ("DYE", "TEMPERATURE", None, 110.0, "OUTSIDE"),
        ("DYE", "TEMPERATURE", 15.0, None, "OUTSIDE"),
        ("DYE", "PH", 1.5, 3.0, "OUTSIDE"),
        ("DYE", "PH", 10.3, 10.5, "WITHIN"),
        ("MORDANT", "TEMPERATURE", 15.0, 100.0, "WITHIN"),
        ("FIRE", "TEMPERATURE", 450.0, 600.0, "OUTSIDE"),
        ("FIRE", "TEMPERATURE", 700.0, 900.0, "WITHIN"),
        ("CAST", "TEMPERATURE", 900.0, 940.0, "WITHIN"),
        ("CAST", "TEMPERATURE", 1250.0, 1250.0, "OUTSIDE"),
        ("DYE", "DURATION", 1.0, 4.0, "NONE"),
        ("WASH", "TEMPERATURE", 30.0, 40.0, "NONE"),
    ],
)
def test_a_reading_is_checked_against_its_stage_envelope(
    stage_type: str, quantity: str, low: float | None, high: float | None, status: str
) -> None:
    check = envelope_check(stage_type, quantity, low, high)
    envelope = envelope_for(stage_type, quantity)
    assert check.status == status
    assert (check.min, check.max) == ((envelope.min, envelope.max) if envelope else (None, None))


def test_each_envelope_names_constants_that_exist() -> None:
    for envelope in STAGE_ENVELOPES.values():
        assert all(key in PHYSICAL_CONSTANTS for key in envelope.basis)


def test_boiling_water_caps_the_aqueous_baths() -> None:
    water = PHYSICAL_CONSTANTS["water-boiling-point"]
    assert envelope_for("DYE", "TEMPERATURE").max == water.max == 100.0
    assert envelope_for("MORDANT", "TEMPERATURE").max == water.max


def test_a_firing_reaches_the_top_of_its_constants_and_casting_holds_brass() -> None:
    fire, cast = envelope_for("FIRE", "TEMPERATURE"), envelope_for("CAST", "TEMPERATURE")
    for key in ("kaolinite-dehydroxylation", "quartz-inversion"):
        constant = PHYSICAL_CONSTANTS[key]
        assert fire.min <= constant.max <= fire.max
    brass = PHYSICAL_CONSTANTS["brass-melting-range"]
    assert cast.min <= brass.min <= brass.max <= cast.max


def test_kaolinite_dehydroxylation_is_the_range_its_thermal_analysis_paper_states() -> None:
    kaolinite = PHYSICAL_CONSTANTS["kaolinite-dehydroxylation"]
    assert (kaolinite.min, kaolinite.max) == (400.0, 700.0)
    claims = {claim["id"]: claim for claim in load_science_seed()["constants"]["claims"]}
    [cite] = claims[kaolinite.claim_key]["sources"]
    assert (cite["sourceId"], cite["quote"]) == (
        "sci:doi:10.1007/s42860-020-00082-w",
        "Dehydroxylation of kaolinite commonly occurs between 400 and 700°C",
    )
    section = plan_text().split("## 7. Science engine", 1)[1].split("\n## ", 1)[0]
    assert "kaolinite dehydroxylation 400–700 °C" in section


def test_each_constant_is_its_own_cited_claim_stating_its_value() -> None:
    claims = {claim["id"]: claim for claim in load_science_seed()["constants"]["claims"]}
    named = sorted(claim["constant"] for claim in claims.values() if "constant" in claim)
    assert named == sorted(PHYSICAL_CONSTANTS)
    for constant in PHYSICAL_CONSTANTS.values():
        claim = claims[constant.claim_key]
        assert claim["constant"] == constant.key
        assert claim["evidenceLevel"] == "PROVISIONAL"
        [cite] = claim["sources"]
        assert cite["quoteCheck"] == "PASS"
        for value in {constant.min, constant.max}:
            assert f"{value:g}" in cite["quote"]
            assert f"{value:g}" in claim["text"]
