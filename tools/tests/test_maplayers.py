from __future__ import annotations

import json
from pathlib import Path

import pytest

from basemap.polyline import decode_records
from maplayers.labels import RANGES, RIVERS, label_angle, line_label, peak_text
from maplayers.minerals import (
    MINERAL_CLASSES,
    STATUSES,
    commodities,
    mineral_class,
    minerals_body,
    site_from_row,
)
from maplayers.sources import BOUNDS, BREAKS

REPO_ROOT = Path(__file__).resolve().parents[2]
LAYERS = REPO_ROOT / "frontend" / "public" / "layers"
SYSTEM = REPO_ROOT / "tools" / "design" / "system.json"


def _asset(name: str) -> dict:
    return json.loads((LAYERS / name).read_text(encoding="utf-8"))


def test_a_label_reads_left_to_right_whichever_way_the_line_runs() -> None:
    assert label_angle(1, 0) == 0.0
    assert label_angle(-1, 0) == 0.0
    assert label_angle(1, 1) == 45.0
    assert label_angle(-1, -1) == 45.0
    assert label_angle(1, -1) == -45.0


def test_a_steep_label_is_held_at_seventy_five_degrees() -> None:
    assert label_angle(0, 1) == 75.0
    assert label_angle(0.01, -1) == -75.0


def test_a_line_label_sits_at_its_share_of_the_length_along_the_local_direction() -> None:
    x, y, angle = line_label([(0.0, 0.0), (4.0, 0.0), (4.0, 4.0)], 0.75, 0.5)
    assert (x, y) == (4.0, 2.0)
    assert angle == 75.0
    x, y, angle = line_label([(0.0, 0.0), (10.0, 0.0)], 0.25, 1.0)
    assert (x, y, angle) == (2.5, 0.0, 0.0)


def test_a_spot_height_is_named_with_grouped_metres() -> None:
    assert peak_text("Nanda Devi", 7817.0) == "Nanda Devi 7,817 m"
    assert peak_text("Guru Shikhar", 1722.4) == "Guru Shikhar 1,722 m"


def test_commodities_are_read_in_order_once_each() -> None:
    row = {"commod1": "", "commod2": "Lead, Zinc", "commod3": "Zinc, Silver"}
    assert commodities(row) == ("Lead", "Zinc", "Silver")


def test_a_deposit_takes_the_class_of_its_first_listed_commodity() -> None:
    labels = [label for _, label, _ in MINERAL_CLASSES]
    assert labels[mineral_class(["Iron", "Manganese"])] == "Iron"
    assert labels[mineral_class(["Chromium"])] == "Manganese, chromium and alloy metals"
    assert labels[mineral_class(["Aluminum"])] == "Aluminium"
    assert labels[mineral_class(["Gold", "Platinum"])] == "Copper, lead, zinc and precious metals"
    assert labels[mineral_class(["REE", "Zirconium"])] == "Titanium, zirconium and rare earths"
    assert labels[mineral_class(["Graphite"])] == "Industrial minerals"
    assert labels[mineral_class([])] == "Industrial minerals"


def test_a_processing_plant_or_a_row_without_a_commodity_is_not_a_deposit() -> None:
    base = {"dep_id": "7", "site_name": " Cavarem ", "latitude": "15.1251", "longitude": "74.14216"}
    assert site_from_row({**base, "dev_stat": "Plant", "commod1": "Iron"}, "Goa") is None
    assert site_from_row({**base, "dev_stat": "Producer"}, "Goa") is None
    site = site_from_row({**base, "dev_stat": "Producer", "commod1": "Manganese"}, "Goa")
    assert site is not None
    assert (site.name, site.state, site.status, site.longitude) == ("Cavarem", "Goa", "Producer", 74.1422)


def test_an_unlisted_status_is_read_as_unknown() -> None:
    row = {"dep_id": "8", "latitude": "20", "longitude": "80", "dev_stat": "Mill", "commod3": "Copper"}
    site = site_from_row(row, "")
    assert site is not None and site.status == "Unknown"


def test_the_body_writes_each_site_as_a_compact_row() -> None:
    site = site_from_row(
        {
            "dep_id": "9",
            "latitude": "20",
            "longitude": "80",
            "dev_stat": "Prospect",
            "commod1": "Copper, Gold",
        },
        "Odisha",
    )
    assert site is not None
    body = minerals_body([site], {"dataset": "MRDS"})
    assert body["sites"] == [[9, "", "Odisha", 80.0, 20.0, 3, STATUSES.index("Prospect"), "Copper, Gold"]]
    assert [entry["label"] for entry in body["classes"]] == [label for _, label, _ in MINERAL_CLASSES]


def test_the_mineral_classes_match_the_design_tokens() -> None:
    system = json.loads(SYSTEM.read_text(encoding="utf-8"))
    assert system["ramps"]["mineral"]["classes"] == [label for _, label, _ in MINERAL_CLASSES]
    assert len(system["ramps"]["mineral"]["spec"]["light"]) == len(MINERAL_CLASSES)


@pytest.mark.parametrize("name", ["rivers.json", "relief.json", "minerals.json"])
def test_each_layer_file_names_a_public_domain_source(name: str) -> None:
    body = _asset(name)
    source = body.get("source")
    datasets = body.get("datasets", [source] if isinstance(source, dict) else [])
    assert datasets
    assert all(len(row["sha256"]) == 64 and row["url"].startswith("https://") for row in datasets)


def test_every_river_line_lies_in_the_frame() -> None:
    west, south, east, north = BOUNDS
    for group in _asset("rivers.json")["ranks"]:
        for _, points in decode_records(group["lines"], False):
            assert all(
                west - 1e-3 <= x <= east + 1e-3 and south - 1e-3 <= y <= north + 1e-3 for x, y in points
            )


def test_river_and_range_labels_come_from_the_named_lists() -> None:
    rivers = {text for text, _, _ in RIVERS.values()}
    ranges = {text for text, _, _ in RANGES.values()}
    assert {label["text"] for label in _asset("rivers.json")["labels"]} <= rivers
    assert (
        {
            "Himalaya",
            "Karakoram",
            "Western Ghats",
            "Eastern Ghats",
            "Vindhya Range",
            "Satpura Range",
            "Aravalli Range",
            "Deccan Plateau",
        }
        <= {label["text"] for label in _asset("relief.json")["ranges"]}
        <= ranges
    )


def test_the_relief_bands_follow_the_elevation_breaks() -> None:
    relief = _asset("relief.json")
    assert relief["breaks"] == list(BREAKS) == [band["min"] for band in relief["bands"]]
    assert all(band["rings"] for band in relief["bands"])
    assert (LAYERS / "relief-shade.webp").read_bytes()[8:12] == b"WEBP"
