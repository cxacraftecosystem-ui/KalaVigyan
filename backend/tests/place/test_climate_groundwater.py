import pytest
from pydantic import ValidationError

from app.geo.climate import ClimateTrends
from app.geo.datasets import region_dataset
from app.research.blocks_climate import ClimateRiskBlock, GroundwaterValue
from app.research.blocks_place import DistrictRef
from app.research.datasets import DatasetRef
from app.services.climate_risk import climate_risk_block

from ..contracts.phase_b_golden import catalog_dataset
from ..geo.golden_region import dataset_record
from .test_climate_risk import BLOCK_ID, CARVING, builder, climate_ask, golden_climate, meaning_model

CODE = "OGD_GW_RESOURCES_RAJASTHAN_2023"
JAIPUR = DistrictRef(district_lgd=102, name="Jaipur", state_name="Rajasthan")


def table_row() -> DatasetRef:
    return region_dataset(dataset_record(catalog_dataset(CODE)))


def jaipur_stage() -> GroundwaterValue:
    return GroundwaterValue(
        district=JAIPUR,
        dataset_code=CODE,
        variable="stage_of_groundwater_extraction",
        period="2023",
        value=225.93,
        value_text=None,
        unit="%",
        resolution="district, as in the list of districts before the reorganisation",
    )


def test_the_block_shows_the_district_s_groundwater_beside_the_trends_and_cites_both_rows() -> None:
    golden = golden_climate()
    climate = ClimateTrends(tuple(golden.trends), (*golden.datasets, table_row()), (jaipur_stage(),))
    block = climate_risk_block(climate, {}, [], block_id=BLOCK_ID)
    assert block.groundwater == [jaipur_stage()] and block.trends == golden.trends
    assert [dataset.code for dataset in block.datasets] == [*(d.code for d in golden.datasets), CODE]
    assert ClimateRiskBlock.model_validate(block.model_dump(mode="json", by_alias=True)) == block
    assert "Jaipur" in block.shown_labels()


def test_a_groundwater_figure_is_never_shown_without_its_dataset_row() -> None:
    golden = golden_climate()
    climate = ClimateTrends(tuple(golden.trends), tuple(golden.datasets), (jaipur_stage(),))
    with pytest.raises(ValidationError, match=f"cites the dataset rows it draws: {CODE} missing"):
        climate_risk_block(climate, {}, [], block_id=BLOCK_ID)


async def test_a_district_with_groundwater_and_no_trend_still_gets_a_block(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    water_only = ClimateTrends((), (table_row(),), (jaipur_stage(),))
    model = meaning_model([])
    built = await builder(model, monkeypatch, water_only).build(climate_ask([CARVING]))
    (block,) = built.blocks
    assert (block.trends, block.groundwater, [d.code for d in block.datasets]) == (
        [],
        [jaipur_stage()],
        [CODE],
    )
    assert block.meaning == [] and model.calls == []
