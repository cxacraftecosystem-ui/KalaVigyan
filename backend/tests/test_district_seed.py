import pytest

from app.data.district_register import load_district_register, parse_district_codes
from app.services.district_seed import decode_rings, district_seed_plan, rings_wkt


def test_plan_covers_the_register() -> None:
    plan = district_seed_plan()
    assert len(plan["states"]) == 36
    assert len(plan["districts"]) == 786
    assert sum(1 for row in plan["districts"] if row["lines"]) == 752
    lgds = [row["lgd"] for row in plan["districts"]]
    assert lgds == sorted(set(lgds))
    states = {row["lgd"] for row in plan["states"]}
    assert all(row["state_lgd"] in states for row in plan["districts"])


def test_every_drawn_district_has_a_centroid_inside_india() -> None:
    for row in district_seed_plan()["districts"]:
        if row["lines"] is None:
            assert row["lon"] is None
            continue
        assert 60 < row["lon"] < 100
        assert 5 < row["lat"] < 40


def test_rings_close_and_render_as_multilinestring() -> None:
    plan = district_seed_plan()
    mahe = next(row for row in plan["districts"] if row["lgd"] == 599)
    assert mahe["lines"].startswith("MULTILINESTRING((")
    for ring in mahe["lines"][len("MULTILINESTRING(") : -1].split("), ("):
        points = ring.strip("()").split(", ")
        assert points[0] == points[-1]
        assert len(points) >= 4


def test_decode_stops_at_zero_count_and_skips_short_rings() -> None:
    assert decode_rings("") == []
    assert decode_rings("A") == []
    assert rings_wkt([]) is None


def test_the_seed_names_the_states_and_districts_the_register_loader_reads() -> None:
    plan = district_seed_plan()
    register = load_district_register()
    names = {row["lgd"]: row["name"] for row in plan["states"]}
    assert set(names.values()) == register.states
    seeded = {(names[row["state_lgd"]], row["name"]) for row in plan["districts"]}
    listed = {(state, name) for state, found in register.districts.items() for name in found}
    assert seeded <= listed and len(seeded) == len(plan["districts"])


def test_the_register_refuses_a_district_of_no_listed_state_and_a_repeated_name() -> None:
    states = [{"lgd": 24, "name": "Gujarat"}]
    with pytest.raises(ValueError, match="names state 9"):
        parse_district_codes({"states": states, "districts": [{"lgd": 1, "stateLgd": 9, "name": "Kachchh"}]})
    twice = [{"lgd": 1, "stateLgd": 24, "name": "Kachchh"}, {"lgd": 2, "stateLgd": 24, "name": "Kachchh"}]
    with pytest.raises(ValueError, match="repeats 'Kachchh' of Gujarat"):
        parse_district_codes({"states": states, "districts": twice})
