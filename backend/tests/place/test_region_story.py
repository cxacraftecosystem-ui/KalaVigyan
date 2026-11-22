import dataclasses
import logging
from collections.abc import Sequence
from typing import Any

import pytest
from pydantic import ValidationError

from app.composer.region_story import StoryChoice, StoryStepChoice
from app.core.errors import ExternalFailure
from app.research import explainer
from app.research.blocks_place import RegionStoryBlock
from app.research.datasets import BOUNDARY_DATASET_CODE, DatasetRef
from app.research.rivers import HYDRORIVERS_DATASET_CODE
from app.research.structured import schema_problems
from app.services import place_builders
from app.services.block_builders import BLOCK_BUILDERS
from app.services.chapter_why import story_choice
from app.services.place_builders import RegionStoryBuilder
from app.services.region_story import RegionOffer, region_story_block, story_statements

from .fixtures import (
    GOLDEN_REPLY,
    KACHCHH,
    cited_water,
    codes,
    dataset_rows,
    expected_story,
    golden_story,
    kachchh_offer,
    place_ask,
    place_tools,
    story_model,
)

BLOCK_ID = "s1.region"


@pytest.fixture
def stored(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    found: dict[str, Any] = {"loaded": True, "offer": kachchh_offer(), "asked": []}

    async def loaded(session: Any) -> bool:
        return found["loaded"]

    async def offer(session: Any, craft_slug: str, *, texts: Sequence[str] = ()) -> RegionOffer | None:
        found["asked"].append(craft_slug)
        return found["offer"]

    monkeypatch.setattr(place_builders, "rivers_loaded", loaded)
    monkeypatch.setattr(place_builders, "region_offer", offer)
    return found


def reply(**changes: Any) -> dict[str, Any]:
    return {**GOLDEN_REPLY, **changes}


async def story(stored: dict[str, Any], *replies: dict[str, Any]) -> Any:
    built = await RegionStoryBuilder(place_tools(story_model(*replies))).build(place_ask())
    return built.blocks[0] if built.blocks else None


async def test_kachchh_s_story_follows_the_fixture_reaches_with_cited_steps(stored: dict[str, Any]) -> None:
    model = story_model()
    built = await RegionStoryBuilder(place_tools(model)).build(place_ask())
    (block,) = built.blocks
    assert block.model_dump(mode="json", by_alias=True) == expected_story(BLOCK_ID)
    assert (block.river.reach_ids, block.river.district_lgds) == ([1, 2, 3], [KACHCHH])
    assert built.sources == {}
    assert stored["asked"] == ["Kutch-Ajrakh"]
    (call,) = model.calls
    assert schema_problems(call["schema"]) == []
    for ref, label in (("r1", "river"), (f"d{KACHCHH}", "district"), ("river-density", "map layer")):
        assert f'<untrusted_source ref="{ref}" label="{label}">' in call["user"]
    assert call["user"].count('label="statement">') == 4
    assert "Strahler stream order 3; mean discharge 1.2 m3/s." in call["user"]


async def test_a_step_with_no_claim_is_dropped(stored: dict[str, Any]) -> None:
    steps = [{"claim": "c9", "district": "d449"}, {"claim": "c2", "district": "d449"}]
    block = await story(stored, reply(steps=steps))
    assert [step.sentence.id for step in block.steps] == [f"{BLOCK_ID}.1"]
    assert block.steps[0].sentence.text.startswith("The river Saran in Dhamadka")
    assert await story(stored, reply(steps=[{"claim": "c9", "district": "d449"}])) is None


async def test_a_step_placed_outside_the_story_keeps_its_claim_without_a_district(
    stored: dict[str, Any],
) -> None:
    steps = [{"claim": "c2", "district": "d999"}, {"claim": "c1", "district": "none"}]
    block = await story(stored, reply(steps=steps))
    assert [step.district_lgd for step in block.steps] == [None, None]


async def test_a_missing_dataset_row_drops_its_value(stored: dict[str, Any]) -> None:
    layers = ["soil-ph-0-5cm", "river-density"]
    full = await story(stored, reply(layers=layers))
    assert (full.layers, codes(full.datasets)) == (
        layers,
        [BOUNDARY_DATASET_CODE, HYDRORIVERS_DATASET_CODE, "SOILGRIDS_2_0"],
    )
    rows = {code: row for code, row in dataset_rows().items() if code != "SOILGRIDS_2_0"}
    stored["offer"] = kachchh_offer(datasets=rows)
    without_soil = await story(stored, reply(layers=layers))
    assert (without_soil.layers, codes(without_soil.datasets)) == (
        ["river-density"],
        [BOUNDARY_DATASET_CODE, HYDRORIVERS_DATASET_CODE],
    )
    no_hydro = {code: row for code, row in rows.items() if code != HYDRORIVERS_DATASET_CODE}
    stored["offer"] = kachchh_offer(datasets=no_hydro)
    without_river = await story(stored, reply(layers=layers))
    assert (without_river.river, without_river.layers, codes(without_river.datasets)) == (
        None,
        [],
        [BOUNDARY_DATASET_CODE],
    )
    assert [step.district_lgd for step in without_river.steps] == [None] * 4


def test_a_step_is_placed_only_in_a_district_its_sentence_or_quotes_name() -> None:
    stated = story_statements(place_ask().blocks, cited_water())
    named = dataclasses.replace(stated["c1"], text=f"In Kachchh, {stated['c1'].text}")
    choice = StoryChoice.model_validate(GOLDEN_REPLY)
    block = region_story_block(kachchh_offer(), {"c1": named, "c2": stated["c2"]}, choice, block_id=BLOCK_ID)
    assert [step.district_lgd for step in block.steps] == [KACHCHH, None]
    stored = block.model_dump(mode="json", by_alias=True)
    stored["steps"][1]["districtLgd"] = KACHCHH
    with pytest.raises(ValidationError, match="only in a district its sentence or quotes name"):
        RegionStoryBlock.model_validate(stored)


async def test_without_the_boundary_row_no_story_is_told(stored: dict[str, Any]) -> None:
    rows = {code: row for code, row in dataset_rows().items() if code != BOUNDARY_DATASET_CODE}
    stored["offer"] = kachchh_offer(datasets=rows)
    assert await story(stored) is None


OSM_NAMES = DatasetRef(
    code="OSM_RIVER_NAMES",
    title="OpenStreetMap river names (waterway=river, India extract)",
    publisher="OpenStreetMap contributors, India extract by Geofabrik",
    edition="2026-11-23",
    period="2026-11-23",
    native_resolution="way geometry, matched to HydroRIVERS reaches within 1 km",
    licence="ODbL 1.0",
    licence_url="https://opendatacommons.org/licenses/odbl/1-0/",
    attribution="© OpenStreetMap contributors",
    citation=None,
    url="https://download.geofabrik.de/asia/india-latest.osm.pbf",
)


def named_offer(datasets: dict[str, DatasetRef]) -> RegionOffer:
    offer = kachchh_offer(datasets=datasets)
    (river,) = offer.rivers
    named = dataclasses.replace(river, name="Suran River", name_dataset=OSM_NAMES.code)
    return dataclasses.replace(offer, rivers=(named,))


async def test_an_unnamed_river_is_drawn_unnamed(stored: dict[str, Any]) -> None:
    block = await story(stored)
    assert block.steps[1].sentence.text.startswith("The river Saran in Dhamadka")
    assert block.river.name is None


async def test_a_river_the_names_dataset_names_is_drawn_with_that_name_citing_its_row(
    stored: dict[str, Any],
) -> None:
    stored["offer"] = named_offer({**dataset_rows(), OSM_NAMES.code: OSM_NAMES})
    block = await story(stored)
    assert block.river.name == "Suran River"
    assert codes(block.datasets)[:3] == [BOUNDARY_DATASET_CODE, HYDRORIVERS_DATASET_CODE, OSM_NAMES.code]
    stored["offer"] = named_offer(dataset_rows())
    unnamed = await story(stored)
    assert unnamed.river.name is None and OSM_NAMES.code not in codes(unnamed.datasets)


async def test_no_river_data_adds_no_block_and_logs_once(
    stored: dict[str, Any], caplog: pytest.LogCaptureFixture
) -> None:
    stored["loaded"] = False
    model = story_model()
    builder = RegionStoryBuilder(place_tools(model))
    with caplog.at_level(logging.INFO, logger=place_builders.__name__):
        first = await builder.build(place_ask())
        second = await builder.build(place_ask())
    assert (first.blocks, second.blocks, model.calls, stored["asked"]) == ((), (), [], [])
    notes = [record for record in caplog.records if "not loaded" in record.getMessage()]
    assert len(notes) == 1


async def test_no_story_for_any_craft_or_without_districts(stored: dict[str, Any]) -> None:
    model = story_model()
    assert (await RegionStoryBuilder(place_tools(model)).build(place_ask(craft=False))).blocks == ()
    stored["offer"] = None
    assert (await RegionStoryBuilder(place_tools(model)).build(place_ask())).blocks == ()
    assert model.calls == []


async def test_a_reply_off_its_schema_fails_the_builder(stored: dict[str, Any]) -> None:
    with pytest.raises(ExternalFailure, match="off its schema"):
        await story(stored, {"river": "r1", "riverName": "Saran", "steps": [], "layers": []})


async def test_the_story_is_a_built_kind_the_explainer_accepts(stored: dict[str, Any]) -> None:
    block = await story(stored)
    assert "region_story" in explainer.BUILT_BLOCK_KINDS
    event = explainer.BlockEvent.model_validate({"sectionId": "s1", "block": block.model_dump(by_alias=True)})
    assert event.block == block


async def test_a_reused_section_without_a_stored_story_gets_one_built(stored: dict[str, Any]) -> None:
    assert next(entry for entry in BLOCK_BUILDERS if entry.kind == "region_story").rebuilt_on_reuse
    assert await story(stored) is not None


async def test_a_section_that_already_carries_a_stored_story_builds_no_second(stored: dict[str, Any]) -> None:
    kept = RegionStoryBlock.model_validate(golden_story())
    ask = place_ask()
    ask = dataclasses.replace(ask, blocks=(*ask.blocks, kept))
    model = story_model()
    assert (await RegionStoryBuilder(place_tools(model)).build(ask)).blocks == ()
    assert stored["asked"] == []


def test_a_page_story_over_many_places_and_factors_stays_within_the_choice_s_limits() -> None:
    steps = [StoryStepChoice(claim=f"c{n}", district=f"lgd:{n}") for n in range(1, 26)]
    layers = [f"layer-{n}" for n in range(1, 13)]
    choice = story_choice(steps, layers)
    assert (len(choice.steps), len(choice.layers)) == (20, 10)
    assert (choice.steps, choice.layers) == (steps[:20], layers[:10])
