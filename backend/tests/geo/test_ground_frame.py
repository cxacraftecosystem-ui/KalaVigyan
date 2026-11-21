import pytest

from app.geo.ground_frame import clip_line, clip_ring, framed, place_box, thinned

from .ground_fixtures import ORIGIN, fixture_layers, square

BOX = (0.0, 0.0, 10.0, 10.0)


def area(ring: list[tuple[float, float]]) -> float:
    return (
        abs(sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(ring, [*ring[1:], ring[0]], strict=True))) / 2
    )


def test_a_ring_half_outside_the_frame_keeps_the_half_inside() -> None:
    clipped = clip_ring(square(5.0, 2.0, 15.0, 6.0), BOX)
    assert area(clipped) == pytest.approx(20.0)
    assert all(0.0 <= x <= 10.0 and 0.0 <= y <= 10.0 for x, y in clipped)
    assert clip_ring(square(20.0, 20.0, 30.0, 30.0), BOX) == []


def test_a_line_through_the_frame_keeps_the_part_inside_and_splits_where_it_leaves() -> None:
    assert clip_line([(-5.0, 5.0), (15.0, 5.0)], BOX) == [[(0.0, 5.0), (10.0, 5.0)]]
    runs = clip_line([(2.0, 2.0), (2.0, 12.0), (8.0, 12.0), (8.0, 2.0)], BOX)
    assert runs == [[(2.0, 2.0), (2.0, 10.0)], [(8.0, 10.0), (8.0, 2.0)]]
    assert clip_line([(20.0, 0.0), (30.0, 0.0)], BOX) == []


def test_a_single_place_is_framed_square_with_its_radius_and_an_eight_per_cent_margin() -> None:
    assert place_box([ORIGIN], 50) == (76.445, 19.478, 77.555, 20.522)


def test_a_wide_spread_of_places_is_framed_no_wider_than_the_widest_aspect() -> None:
    west, south, east, north = place_box([(70.0, 20.0), (90.0, 20.0)], 50)
    assert (east - west) * 0.9397 / (north - south) == pytest.approx(1.8, abs=0.01)


def test_thinning_keeps_the_ends_and_drops_points_closer_than_a_step() -> None:
    points = [(0.0, 0.0), (0.0001, 0.0), (0.5, 0.0), (0.5002, 0.0), (1.0, 0.0)]
    assert thinned(points, 0.01, closed=False) == [(0.0, 0.0), (0.5, 0.0), (1.0, 0.0)]
    assert thinned([(0.0, 0.0), (0.0001, 0.0)], 0.01, closed=True) == []


def test_the_frame_holds_the_layers_inside_it() -> None:
    frame = framed(fixture_layers(), place_box([ORIGIN], 50))
    assert [band.low_m for band in frame.bands] == [100, 300]
    assert frame.bands[0].rings == [square(76.5, 19.5, 77.5, 20.5)]
    assert [(line.rank, line.points) for line in frame.rivers] == [(4, [(77.1, 19.8), (77.1, 20.2)])]
    assert frame.lakes == [square(77.3, 20.3, 77.4, 20.4)]
    assert [label.text for label in frame.labels] == ["Fixture"]
