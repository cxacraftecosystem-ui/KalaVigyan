import pytest

from app.geo.ground_layers import Band, Deposit, decode_records, line_of
from app.geo.ground_measure import elevation_band, haversine_km, inside, nearest_lake, nearest_line, within

from .ground_fixtures import ORIGIN, square

ONE_DEGREE_KM = 111.19508
TENTH_EAST_AT_20N_KM = 10.4489
LAKE_CORNER_KM = 45.7551


def deposit(dep_id: int, longitude: float, latitude: float) -> Deposit:
    return Deposit(dep_id, f"site {dep_id}", longitude, latitude, 0, "Occurrence", ("Iron",))


def test_a_hand_encoded_payload_decodes_to_its_points_and_records() -> None:
    assert decode_records("ECEGA") == [[(0.001, 0.002), (0.004, 0.002)]]
    assert decode_records("CgBB") == [[(0.016, -0.001)]]
    assert decode_records("CCECCA") == [[(0.001, 0.002)], [(0.002, 0.002)]]


def test_a_degree_of_latitude_is_the_great_circle_length_of_one_degree() -> None:
    assert haversine_km((0.0, 0.0), (0.0, 1.0)) == pytest.approx(ONE_DEGREE_KM, abs=1e-3)
    assert haversine_km(ORIGIN, ORIGIN) == 0.0


def test_the_nearest_river_is_the_closest_point_on_its_nearest_line() -> None:
    near = line_of([(77.1, 19.8), (77.1, 20.2)], rank=4)
    far = line_of([(78.0, 19.0), (78.0, 21.0)], rank=1)
    found = nearest_line(ORIGIN, [far, near])
    assert found is not None
    assert found.distance_km == pytest.approx(TENTH_EAST_AT_20N_KM, abs=1e-3)
    assert found.at == pytest.approx((77.1, 20.0))
    assert found.rank == 4


def test_past_the_end_of_a_line_the_distance_runs_to_its_end_point() -> None:
    found = nearest_line(ORIGIN, [line_of([(77.0, 20.1), (77.0, 20.3)])])
    assert found is not None
    assert found.at == pytest.approx((77.0, 20.1))
    assert found.distance_km == pytest.approx(ONE_DEGREE_KM / 10, abs=1e-3)


def test_a_hole_inside_a_ring_is_outside_it() -> None:
    rings = [line_of(square(76.0, 19.0, 78.0, 21.0)), line_of(square(76.9, 19.9, 77.1, 20.1))]
    assert not inside(ORIGIN, rings)
    assert inside((76.5, 19.5), rings)
    assert not inside((80.0, 20.0), rings)


def test_the_nearest_lake_is_its_nearest_shore_or_nothing_from_inside_it() -> None:
    lake = [line_of(square(77.3, 20.3, 77.4, 20.4))]
    found = nearest_lake(ORIGIN, lake)
    assert found is not None
    assert found.at == pytest.approx((77.3, 20.3))
    assert found.distance_km == pytest.approx(LAKE_CORNER_KM, abs=2e-3)
    held = nearest_lake((77.35, 20.35), lake)
    assert held is not None and held.distance_km == 0.0


def test_the_band_is_the_highest_break_whose_area_holds_the_place() -> None:
    bands = [
        Band(100, (line_of(square(76.5, 19.5, 77.5, 20.5)),)),
        Band(300, (line_of(square(76.9, 19.9, 77.05, 20.05)),)),
        Band(600, ()),
    ]
    breaks = (100, 300, 600)
    assert elevation_band(ORIGIN, bands, breaks) == (300, 600)
    assert elevation_band((77.4, 20.4), bands, breaks) == (100, 300)
    assert elevation_band((80.0, 20.0), bands, breaks) == (None, 100)
    top = [Band(100, (line_of(square(76.0, 19.0, 78.0, 21.0)),))]
    assert elevation_band(ORIGIN, top, (100,)) == (100, None)


def test_deposits_within_the_radius_come_nearest_first() -> None:
    sites = [deposit(1, 77.0, 20.3), deposit(2, 77.0, 20.6), deposit(3, 77.0, 20.1), deposit(4, 79.0, 20.0)]
    found = within(ORIGIN, sites, 50)
    assert [(site.dep_id, round(km, 2)) for site, km in found] == [(3, 11.12), (1, 33.36)]
