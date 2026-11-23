import json
from typing import Any

import pytest
from pydantic import ValidationError

from app.research.blocks_place import SupplyLink, SupplyMapBlock
from app.research.datasets import BOUNDARY_DATASET_CODE

from .blocks_golden import SUPPLY_DISTRICT, BlocksFixture
from .golden import REPO, golden_json, reproduces

GANDHINAGAR = 446


def block() -> dict[str, Any]:
    (section,) = golden_json(SUPPLY_DISTRICT)["sections"]
    (found,) = section["blocks"]
    return found


def test_the_district_placed_supply_golden_is_reproduced_byte_for_byte() -> None:
    assert reproduces(BlocksFixture, SUPPLY_DISTRICT)


def test_an_origin_the_register_holds_is_pinned_at_its_district_s_stored_centroid() -> None:
    shapes = json.loads(
        (REPO / "backend" / "app" / "data" / "district-shapes.json").read_text(encoding="utf-8")
    )
    longitude, latitude = next(row["centroid"] for row in shapes["districts"] if row["lgd"] == GANDHINAGAR)
    (link,) = SupplyMapBlock.model_validate(block()).links
    assert (link.origin, link.district_lgd, link.wikidata_id) == ("Gandhinagar", GANDHINAGAR, None)
    assert (link.latitude, link.longitude) == (latitude, longitude)
    assert [row.code for row in SupplyMapBlock.model_validate(block()).datasets] == [BOUNDARY_DATASET_CODE]


@pytest.mark.parametrize(
    ("change", "refusal"),
    [
        (lambda b: b["links"][0].update(wikidataId="Q1"), "by Wikidata or by its register district"),
        (lambda b: b["links"][0].update(latitude=None, longitude=None), "only where it is placed"),
        (lambda b: b["links"][0].update(longitude=None), "both coordinates"),
        (lambda b: b.update(datasets=[]), f"cites {BOUNDARY_DATASET_CODE} exactly when"),
    ],
)
def test_a_district_placement_without_its_parts_is_refused(change: Any, refusal: str) -> None:
    body = block()
    change(body)
    with pytest.raises(ValidationError, match=refusal):
        SupplyMapBlock.model_validate(body)


def test_a_wikidata_placed_map_cites_no_dataset_and_leaves_the_new_fields_out() -> None:
    body = block()
    body["links"][0].update(districtLgd=None, wikidataId="Q1", latitude=23.2, longitude=72.6)
    body["datasets"] = []
    plain = SupplyMapBlock.model_validate(body).model_dump(mode="json", by_alias=True)
    assert "datasets" not in plain and "districtLgd" not in plain["links"][0]
    with pytest.raises(ValidationError, match="exactly when"):
        SupplyMapBlock.model_validate({**body, "datasets": block()["datasets"]})
    assert SupplyLink.model_validate(body["links"][0]).district_lgd is None
