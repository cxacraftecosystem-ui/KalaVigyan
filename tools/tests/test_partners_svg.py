from __future__ import annotations

from partners.raster import fitted_size
from partners.svg import compact_path, minified_svg, number_text, subpaths


def test_numbers_drop_zeros_and_their_leading_zero() -> None:
    assert [number_text(v) for v in (0.5, -0.25, 3.0, 0.0, -0.0001, 12.3456)] == [
        ".5",
        "-.25",
        "3",
        "0",
        "0",
        "12.346",
    ]


def test_relative_lines_become_absolute_points() -> None:
    assert subpaths("m10 10l5 0h-2v4z") == [[(10.0, 10.0), (15.0, 10.0), (13.0, 10.0), (13.0, 14.0)]]


def test_a_relative_move_after_a_close_starts_from_the_last_start() -> None:
    found = subpaths("M0 0h4v4h-4zm10 0h2v2h-2z")
    assert found[1][0] == (10.0, 0.0)


def test_a_square_keeps_its_corners_and_drops_collinear_points() -> None:
    assert compact_path("M0 0h1h1v2h-2z", 1.0) == "M0 0h2v2h-2z"


def test_rounding_does_not_drift_along_a_long_relative_path() -> None:
    steps = "l.04 0" * 100
    path = compact_path(f"M0 0{steps}v1z", 0.1)
    assert path == "M0 0h4v1z"


def test_the_second_subpath_moves_relative_to_the_first_start() -> None:
    assert compact_path("M0 0h2v2h-2zM5 5h2v2h-2z", 1.0) == "M0 0h2v2h-2zm5 5h2v2h-2z"


def test_the_minified_file_keeps_the_size_fill_and_rule() -> None:
    source = (
        '<?xml version="1.0"?><svg xmlns="http://www.w3.org/2000/svg" width="20.5" height="10">'
        '<metadata>x</metadata><g fill="#291973" fill-rule="evenodd"><path d="M0 0h2v2h-2z"/></g></svg>'
    )
    assert minified_svg(source, 1.0) == (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 20.5 10" width="20.5" height="10">'
        '<g fill="#291973" fill-rule="evenodd"><path d="M0 0h2v2h-2z"/></g></svg>\n'
    )


def test_a_wide_mark_is_scaled_to_the_web_width() -> None:
    assert fitted_size((2628, 970), 600) == (600, 221)
    assert fitted_size((300, 100), 600) == (300, 100)
