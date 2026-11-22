import re

import pytest

from app.core.errors import InvalidInput
from app.research.component_specs_plates_parts import UNIT_REF_PATTERN as PLATE_REFS
from app.research.component_specs_science_parts import UnitRef as ScienceRef
from app.research.component_specs_tools import UNIT_REF_PATTERN as TOOL_REFS
from app.research.unit_ids import AUTHORED_UNITS, DELIVERED_UNITS, PLATE_UNITS, UNIT_REF_PATTERN


def test_every_spec_names_its_units_by_the_one_pattern() -> None:
    assert PLATE_REFS == TOOL_REFS == UNIT_REF_PATTERN == r"^u\d{4}$"
    assert ScienceRef.__metadata__[0].metadata[0].pattern == UNIT_REF_PATTERN
    assert [
        bool(re.match(UNIT_REF_PATTERN, unit)) for unit in ("u0001", "u9001", "u10001", "chemistry-ab12")
    ] == [
        True,
        True,
        False,
        False,
    ]


def test_authored_delivered_and_picture_units_take_their_own_numbers() -> None:
    assert (AUTHORED_UNITS.unit(0), DELIVERED_UNITS.unit(0), PLATE_UNITS.unit(0)) == (
        "u0001",
        "u5001",
        "u9001",
    )
    assert [PLATE_UNITS.holds(unit) for unit in ("u9001", "u9999", "u8999", "plate-1")] == [
        True,
        True,
        False,
        False,
    ]
    assert AUTHORED_UNITS.holds("u1113") and not AUTHORED_UNITS.holds("u5001")
    assert PLATE_UNITS.fresh(2, {"u9001"}) == ["u9002", "u9003"]
    with pytest.raises(InvalidInput, match="no more room for picture units"):
        PLATE_UNITS.unit(999)
