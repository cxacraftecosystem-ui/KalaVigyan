import pytest

from app.research.review_queue_readings import reading_origin
from app.science.reading_checks import enveloped, reading_check
from app.science.units import Bounds


@pytest.mark.parametrize(
    ("read", "stated", "unit", "status", "bounds"),
    [
        (("DYE", "TEMPERATURE"), Bounds(130.0, 130.0), "°C", "OUTSIDE", (130.0, 130.0)),
        (("DYE", "TEMPERATURE"), Bounds(60.0, 60.0), "°C", "WITHIN", (60.0, 60.0)),
        (("DYE", "TEMPERATURE"), Bounds(None, 266.0), "degF", "OUTSIDE", (None, 130.0)),
        (("DYE", "TEMPERATURE"), Bounds(140.0, 140.0), "degF", "WITHIN", (60.0, 60.0)),
        (("FIRE", "TEMPERATURE"), Bounds(450.0, 450.0), "°C", "OUTSIDE", (450.0, 450.0)),
        (("DYE", "PH"), Bounds(13.0, 13.0), "pH", "OUTSIDE", (13.0, 13.0)),
        (("DYE", "DURATION"), Bounds(2.0, 2.0), "h", "NONE", (2.0, 2.0)),
        (("PREP", "TEMPERATURE"), Bounds(130.0, 130.0), "°C", "NONE", (130.0, 130.0)),
    ],
)
def test_a_reading_is_outside_when_a_bound_leaves_its_stage_s_range_once_converted(
    read: tuple[str, str], stated: Bounds, unit: str, status: str, bounds: tuple[float | None, ...]
) -> None:
    stage_type, quantity = read
    checked = reading_check(stage_type, quantity, stated, unit)
    assert checked.envelope.status == status
    assert (checked.bounds.low, checked.bounds.high) == bounds
    assert checked.outside is (status == "OUTSIDE")


def test_only_the_stage_types_and_quantities_with_a_range_are_checked() -> None:
    assert enveloped() == (
        ("CAST", "TEMPERATURE"),
        ("DYE", "PH"),
        ("DYE", "TEMPERATURE"),
        ("FIRE", "TEMPERATURE"),
        ("MORDANT", "TEMPERATURE"),
    )


@pytest.mark.parametrize(
    ("claim_origin", "found_by", "origin"),
    [
        ("IMPORT", [None], "RESEARCH"),
        ("LIVE_RESEARCH", ["ANSWER"], "RESEARCH"),
        ("CONTRIBUTION", ["USER"], "CONTRIBUTION"),
        ("CONTRIBUTION", ["AGENT"], "AGENT"),
        ("IMPORT", ["AGENT"], "AGENT"),
    ],
)
def test_a_reading_arrives_by_its_fact_s_origin(
    claim_origin: str, found_by: list[str | None], origin: str
) -> None:
    assert reading_origin(claim_origin, found_by) == origin
