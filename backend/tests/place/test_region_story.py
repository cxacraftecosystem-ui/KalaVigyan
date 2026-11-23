import dataclasses
import logging
import uuid
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from app.composer.region_story import StoryChoice, StoryStepChoice
from app.core.errors import ExternalFailure
from app.research import explainer
from app.research.blocks_place import RegionStoryBlock
from app.research.citations import Citation
from app.research.datasets import BOUNDARY_DATASET_CODE, DatasetRef
from app.research.knowledge_pieces import KnowledgePiece, PieceSlot, knowledge_piece, piece_slot
from app.research.rivers import HYDRORIVERS_DATASET_CODE
from app.research.structured import schema_problems
from app.science.records import KnownClaim
from app.services import place_builders
from app.services.answer_events import CitedClaims
from app.services.block_builders import BLOCK_BUILDERS, BlockBuilders
from app.services.chapter_why import story_choice
from app.services.place_builders import RegionStoryBuilder, with_place_claims
from app.services.place_claims import PlaceClaims
from app.services.region_story import RegionOffer, region_story_block, story_statements

from ..contracts.phase_b_golden import phase_b
from .fixtures import (
    GOLDEN_REPLY,
    KACHCHH,
    StoryReads,
    cited_water,
    codes,
    dataset_rows,
    expected_story,
    golden_story,
    kachchh_offer,
    kachchh_ref,
    patch_story_reads,
    place_ask,
    place_tools,
    story_model,
    visible,
)

BLOCK_ID = "s1.region"
KEPT_AT = datetime(2026, 11, 17, 9, 0, tzinfo=UTC)
KACHCHH_TEXT = "In Kachchh, printers drew water from wells near Dhamadka."
KACHCHH_QUOTE = "printers drew water from wells near Dhamadka in Kachchh"


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
    found["reads"] = patch_story_reads(monkeypatch, StoryReads())
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
    assert block.river.reach_ids == golden_story()["river"]["reachIds"] and block.river.district_lgds == [
        KACHCHH
    ]
    assert block.river.reach_ids[-1] == block.river.main_riv == 41063203
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


def test_a_step_naming_its_district_by_another_name_the_register_lists_is_placed_there() -> None:
    stated = story_statements(place_ask().blocks, cited_water())
    aliased = dataclasses.replace(stated["c1"], text=f"In Kutch, {stated['c1'].text}")
    choice = StoryChoice.model_validate(GOLDEN_REPLY)
    block = region_story_block(
        kachchh_offer(), {"c1": aliased, "c2": stated["c2"]}, choice, block_id=BLOCK_ID
    )
    assert kachchh_ref().other_names == ["Kutch"]
    assert [step.district_lgd for step in block.steps] == [KACHCHH, None]
    stored = block.model_dump(mode="json", by_alias=True)
    assert stored["districts"] == [
        {"districtLgd": KACHCHH, "name": "Kachchh", "stateName": "Gujarat", "otherNames": ["Kutch"]}
    ]
    del stored["districts"][0]["otherNames"]
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


def stored_story(*, depth: str = "EXPERT") -> KnowledgePiece:
    block = RegionStoryBlock.model_validate(golden_story())
    slot = PieceSlot(None, "GEOGRAPHY", f"water:lgd-{KACHCHH}", depth)
    return knowledge_piece(
        block,
        piece_slot(block, slot),
        piece_id=uuid.UUID(int=41),
        answer_id=uuid.UUID(int=42),
        created_at=KEPT_AT,
    )


def golden_sources(source_ids: Iterable[str]) -> dict[str, dict[str, Any]]:
    sources = {source["id"]: source for source in phase_b()["sources"]}
    return {source_id: sources[source_id] for source_id in source_ids}


async def test_a_current_stored_story_is_placed_with_its_mark_and_asks_no_model(
    stored: dict[str, Any],
) -> None:
    piece = stored_story()
    reads = stored["reads"]
    reads.stories, reads.states = [piece], visible(piece)
    reads.cited = CitedClaims(sources=golden_sources(piece.payload.cited_source_ids()))
    model = story_model()
    built = await RegionStoryBuilder(place_tools(model)).build(place_ask())
    (block,) = built.blocks
    assert (block.id, block.reuse.piece_id, block.reuse.stored_at) == (BLOCK_ID, piece.id, KEPT_AT)
    assert block.steps == piece.payload.steps
    assert model.calls == [] and stored["asked"] == []
    assert sorted(built.sources) == sorted(set(piece.payload.cited_source_ids()))
    (entry,) = [entry for entry in BLOCK_BUILDERS if entry.kind == "region_story"]
    added = await BlockBuilders([(entry, RegionStoryBuilder(place_tools(story_model())))]).added(place_ask())
    assert [(block.kind, block.reuse.piece_id) for block in added.blocks] == [("region_story", piece.id)]


async def test_a_stored_story_that_fails_the_reuse_rule_is_told_again(stored: dict[str, Any]) -> None:
    piece = stored_story(depth="BASIC")
    reads = stored["reads"]
    reads.stories, reads.states = [piece], visible(piece)
    model = story_model()
    built = await RegionStoryBuilder(place_tools(model)).build(place_ask())
    (block,) = built.blocks
    assert block.reuse is None and len(model.calls) == 1
    assert reads.asked[0] == {"stories": ["GEOGRAPHY"]}


def place_fact() -> KnownClaim:
    first = golden_story()["steps"][0]["sentence"]["citations"][0]
    citation = Citation.model_validate(
        {**first, "id": str(uuid.UUID(int=98)), "claimId": str(uuid.UUID(int=99)), "quote": KACHCHH_QUOTE}
    )
    return KnownClaim(uuid.UUID(int=99), KACHCHH_TEXT, "PROVISIONAL", (citation,))


async def test_the_district_s_place_claims_are_offered_after_the_section_s(stored: dict[str, Any]) -> None:
    fact = place_fact()
    source_id = fact.citations[0].source_id
    reads = stored["reads"]
    reads.place = PlaceClaims((fact,), golden_sources([source_id]))
    model = story_model(reply(steps=[{"claim": "c5", "district": f"d{KACHCHH}"}]))
    built = await RegionStoryBuilder(place_tools(model)).build(place_ask())
    (block,) = built.blocks
    assert [(step.district_lgd, step.sentence.text) for step in block.steps] == [(KACHCHH, KACHCHH_TEXT)]
    assert built.sources == golden_sources([source_id])
    (call,) = model.calls
    assert call["user"].count('label="statement">') == 5
    assert f'<untrusted_source ref="c5" label="statement">\n{KACHCHH_TEXT}' in call["user"]
    held = [claim.id for claim in story_statements(place_ask().blocks, cited_water()).values()]
    assert reads.asked[-1] == {"districts": [KACHCHH], "held": held}


def test_place_claims_join_the_statements_once_each_after_the_section_s() -> None:
    section = story_statements(place_ask().blocks, cited_water())
    fact = place_fact()
    joined = with_place_claims(section, (fact, section["c2"], fact))
    assert list(joined) == ["c1", "c2", "c3", "c4", "c5"]
    assert joined["c5"] == fact
