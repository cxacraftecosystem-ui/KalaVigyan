from __future__ import annotations

from pathlib import Path

from basemap.polyline import decode_records, encode_records, encode_ring, india_payload

REPO_ROOT = Path(__file__).resolve().parents[2]
INDIA_SOURCE = REPO_ROOT / "frontend/components/map/indiaGeometry.ts"
INDIA_BOUNDS = (68.2060, 6.7560, 97.3940, 37.0820)


def test_a_whole_degree_is_written_in_three_characters() -> None:
    assert encode_records([[(1.0, 0.0)]]) == "Cw-BA"


def test_a_ring_drops_its_closing_point_and_writes_deltas() -> None:
    ring = [(0.0, 0.0), (0.001, 0.0), (0.001, 0.001), (0.0, 0.0)]
    assert encode_ring(ring) == "GAACAAC"


def test_points_that_round_to_the_same_place_are_written_once() -> None:
    assert encode_records([[(0.0001, 0.0), (0.0002, 0.0)]]) == "CAA"


def test_a_hole_flag_follows_the_count() -> None:
    encoded = encode_records([[(0.0, 0.0)]], holes=[True])
    assert encoded == "CCAA"
    assert decode_records(encoded, True) == [(True, [(0.0, 0.0)])]


def test_negative_steps_decode_back() -> None:
    line = [(68.206, 23.5), (68.1, 23.499), (68.25, 23.6)]
    assert decode_records(encode_records([line]), False) == [(False, line)]


def test_the_payload_is_read_from_its_concatenated_lines() -> None:
    source = 'const PAYLOAD =\n  "abc" +\n  "def";\n'
    assert india_payload(source) == "abcdef"


def test_the_survey_of_india_outline_decodes_inside_india() -> None:
    records = decode_records(india_payload(INDIA_SOURCE.read_text(encoding="utf-8")), True)
    west, south, east, north = INDIA_BOUNDS
    points = [point for _, ring in records for point in ring]
    assert len(records) > 1
    assert all(west - 0.01 <= x <= east + 0.01 and south - 0.01 <= y <= north + 0.01 for x, y in points)
