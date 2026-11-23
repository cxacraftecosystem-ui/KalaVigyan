from typing import Any

import pytest
from pydantic import TypeAdapter

from app.core.errors import InvalidInput
from app.geo.district_view import DistrictLocation, DistrictRecords, district_crafts
from app.geo.headline import headline_rows
from app.geo.records import ValueRecord
from app.research.blocks_place import DistrictRef
from app.research.citations import SourceRef
from app.research.explainer import Block
from app.schemas.district_crafts import DistrictCrafts

from ..contracts.golden import dumped, golden_json, golden_text
from .golden_region import (
    AJRAKH,
    GI_JOURNAL,
    GI_JOURNAL_TITLE,
    KACHCHH,
    dataset_record,
    golden_datasets,
    kachchh_values,
)

DISTRICT_CRAFTS = "map.district-crafts.golden.json"
BAGRU = AJRAKH.model_copy(
    update={"slug": "Bagru-Hand-Block-Print", "name": "Bagru", "path": "/crafts/Bagru-Hand-Block-Print"}
)


def golden() -> dict[str, Any]:
    return golden_json(DISTRICT_CRAFTS)


def region_card_values() -> tuple[ValueRecord, ...]:
    return tuple(headline_rows(kachchh_values(), golden_datasets()))


def location(**changes: Any) -> DistrictLocation:
    fields: dict[str, Any] = {
        "id": "location-kachchh",
        "craft": AJRAKH,
        "role": None,
        "level": "PROVISIONAL",
        "source_id": GI_JOURNAL,
        "source_title": GI_JOURNAL_TITLE,
    }
    return DistrictLocation(**(fields | changes))


def records(**changes: Any) -> DistrictRecords:
    body = golden()
    fields: dict[str, Any] = {
        "district": DistrictRef.model_validate(body["district"]),
        "boundary": dataset_record(body["datasets"][0]),
        "locations": (location(),),
        "values": region_card_values(),
        "datasets": golden_datasets(),
        "blocks": tuple(TypeAdapter(Block).validate_python(block) for block in body["land"]["blocks"]),
        "sources": {source["id"]: SourceRef.model_validate(source) for source in body["sources"]},
    }
    return DistrictRecords(**(fields | changes))


def test_kachchh_s_stored_rows_build_the_golden_district() -> None:
    assert dumped(DistrictCrafts, district_crafts(records())) == golden_text(DISTRICT_CRAFTS)


def test_the_land_shows_only_the_district_s_soil_climate_water_and_terrain() -> None:
    body = district_crafts(records(values=kachchh_values()))
    shown = {value.dataset_code for facet in body.land.facets for value in facet.values}
    assert {row.dataset_code for row in kachchh_values()} - shown == {
        "ESA_WORLDCOVER_2021_V200",
        "GLIM_1_0_05DEG",
        "HANSEN_GFC_2025_V1_13",
        "USGS_MRDS",
    }
    assert [facet.facet for facet in body.land.facets] == ["SOIL", "CLIMATE", "WATER", "TERRAIN"]


def test_a_craft_is_placed_by_its_strongest_location_with_every_role_it_holds() -> None:
    reviewed = location(
        id="location-b", role="ORIGIN", level="REVIEWED", source_id="other", source_title="Survey"
    )
    located = (location(role="HISTORIC_CENTRE"), reviewed, location(id="location-c"))
    body = district_crafts(
        records(locations=located, sources={**records().sources, "other": source("other")})
    )
    (entry,) = body.crafts
    assert entry.roles == ["PRACTISED", "ORIGIN", "HISTORIC_CENTRE"]
    assert (entry.basis.source_id, entry.basis.level, entry.basis.label) == ("other", "REVIEWED", "Survey")


def test_crafts_are_listed_once_each_by_name() -> None:
    located = (location(), location(id="location-bagru", craft=BAGRU), location(id="location-again"))
    assert [entry.craft.slug for entry in district_crafts(records(locations=located)).crafts] == [
        "Bagru-Hand-Block-Print",
        "Kutch-Ajrakh",
    ]


def test_a_district_with_nothing_stored_has_no_land_and_no_crafts() -> None:
    body = district_crafts(records(locations=(), values=(), blocks=(), sources={}))
    assert (body.crafts, body.land, body.sources) == ([], None, [])
    assert [dataset.code for dataset in body.datasets] == ["DR_DISTRICT_SHAPES"]


def test_a_stored_story_citing_a_source_no_longer_shown_is_left_out() -> None:
    sources = dict(records().sources)
    sources.pop("907e2c52-14e7-5e41-9b27-9c10f70906a9")
    body = district_crafts(records(sources=sources))
    assert body.land.blocks == []
    assert [source.id for source in body.sources] == [GI_JOURNAL]


def test_a_value_without_its_dataset_row_fails_loudly() -> None:
    datasets = {code: row for code, row in golden_datasets().items() if code != "SOILGRIDS_2_0"}
    with pytest.raises(InvalidInput, match="SOILGRIDS_2_0"):
        district_crafts(records(datasets=datasets))


def test_the_tapped_district_is_the_register_s() -> None:
    body = district_crafts(records())
    assert (body.district.district_lgd, body.district.name) == (KACHCHH, "Kachchh")


def source(source_id: str) -> SourceRef:
    return SourceRef.model_validate({**golden()["sources"][0], "id": source_id, "title": "Survey"})
