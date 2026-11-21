from dataclasses import replace

import pytest
from pydantic import ValidationError

from app.geo.place_ground import craft_ground, direct_measures, map_place_ground
from app.research.place_ground import GroundReading
from app.research.why_here import CraftGround, WhyHereSpec

from ..contracts.golden import golden_json
from .ground_fixtures import GOLDEN_GROUND, ORIGIN, fixture_inputs, fixture_layers, fixture_place

RAIN = GroundReading(
    reading="rainfall",
    dataset_code="CHIRPS_3_0",
    variable="annual_precipitation",
    depth=None,
    period="1981-2025",
    stat="NORMAL",
    value=449.0,
    unit="mm",
    resolution="0.05 degree",
)


def built() -> CraftGround:
    ground = craft_ground(fixture_inputs(), direct_measures(fixture_layers()))
    assert ground is not None
    return ground


def test_the_fixture_craft_measures_to_the_golden_ground() -> None:
    assert built().model_dump(mode="json", by_alias=True) == golden_json(GOLDEN_GROUND)


def test_the_golden_ground_is_a_valid_why_here_spec_with_no_notes() -> None:
    spec = WhyHereSpec.model_validate({"ground": golden_json(GOLDEN_GROUND), "notes": []})
    [place] = spec.ground.places
    assert (place.ground.elevation.low_m, place.ground.elevation.high_m) == (300, 600)
    assert [(m.material, m.count, m.nearest_km) for m in place.materials] == [
        ("Alum", 1, 33.4),
        ("Iron filings", 1, 11.1),
    ]


def test_a_craft_without_a_located_place_has_no_ground() -> None:
    inputs = replace(fixture_inputs(), places=())
    assert craft_ground(inputs, direct_measures(fixture_layers())) is None


def test_two_places_share_one_frame_and_each_deposit_is_listed_once_at_its_nearest() -> None:
    second = fixture_place(key="place-2", name="Second village", longitude=77.0, latitude=19.75)
    inputs = replace(fixture_inputs(), places=(fixture_place(), second))
    ground = craft_ground(inputs, direct_measures(fixture_layers()))
    assert ground is not None
    assert [(d.dep_id, d.nearest_km) for d in ground.deposits] == [(3, 5.6), (1, 11.1)]
    assert ground.frame.south < 19.75 < ground.frame.north
    assert [source.id for source in ground.sources] == [ground.places[0].source_id]


def test_district_readings_must_cite_their_datasets() -> None:
    inputs = replace(fixture_inputs(), places=(fixture_place(district_lgd=449),), readings={449: (RAIN,)})
    with pytest.raises(ValidationError, match="cite CHIRPS_3_0"):
        craft_ground(inputs, direct_measures(fixture_layers()))


def test_the_map_reads_the_same_ground_at_a_craft_place() -> None:
    found = map_place_ground(ORIGIN, None, direct_measures(fixture_layers()), ((), ()))
    golden = golden_json(GOLDEN_GROUND)["places"][0]["ground"]
    assert found.model_dump(mode="json", by_alias=True)["ground"] == golden
    assert (found.district, found.radius_km, len(found.layers)) == (None, 50, 4)
