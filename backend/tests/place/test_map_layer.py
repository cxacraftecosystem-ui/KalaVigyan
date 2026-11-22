import dataclasses
from typing import Any

import pytest

from app.geo.section_layers import section_layer_order
from app.services import place_builders
from app.services.block_builders import BLOCK_BUILDERS, BlockBuilders
from app.services.place_builders import MapLayerBuilder
from app.services.place_offers import SectionLayer

from ..answering.fakes import (
    SOURCES,
    UNDERSTOOD_REPLY,
    VIEWS,
    FakeResearch,
    pipeline,
    streamed,
    understanding_model,
)
from ..answering.piece_fakes import MemoryPieces
from ..answering.test_answer_flow import REPLY, events
from ..answering.test_piece_reuse_flow import asked
from ..composer.fixtures import replacements
from ..geo.golden_region import golden_layer_values
from .fixtures import KACHCHH, golden_layer, place_ask, place_tools


@pytest.fixture
def offered(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    found: dict[str, Any] = {"layer": SectionLayer(golden_layer_values(), (KACHCHH,)), "asked": []}

    async def section_layer(session: Any, craft_slug: str, discipline: str, texts: Any) -> Any:
        found["asked"].append((craft_slug, discipline, list(texts)))
        return found["layer"]

    monkeypatch.setattr(place_builders, "section_map_layer", section_layer)
    return found


async def test_the_map_layer_is_the_registry_layer_as_its_route_answers_it(offered: dict[str, Any]) -> None:
    built = await MapLayerBuilder(place_tools()).build(place_ask("GEOLOGY", section_id="s2"))
    (block,) = built.blocks
    assert block.model_dump(mode="json", by_alias=True) == {**golden_layer(), "id": "s2.map"}
    assert built.sources == {}
    ((craft, discipline, texts),) = offered["asked"]
    assert (craft, discipline) == ("Kutch-Ajrakh", "GEOLOGY")
    assert texts[1].startswith("The river Saran in Dhamadka")


async def test_no_layer_with_a_value_in_the_craft_s_districts_adds_no_map(offered: dict[str, Any]) -> None:
    offered["layer"] = None
    assert (await MapLayerBuilder(place_tools()).build(place_ask("CLIMATE"))).blocks == ()
    assert (await MapLayerBuilder(place_tools()).build(place_ask("CLIMATE", craft=False))).blocks == ()
    assert len(offered["asked"]) == 1


def test_a_section_s_words_choose_its_layer_first() -> None:
    assert section_layer_order("CLIMATE", ["Dyeing waits for the monsoon to end."])[:2] == [
        "monsoon-share",
        "annual-mean-temperature",
    ]
    assert section_layer_order("CLIMATE", ["Cloth dries fast in the heat.", "Rain is scarce."])[:3] == [
        "warmest-month-maximum",
        "annual-precipitation",
        "annual-mean-temperature",
    ]
    assert section_layer_order("GEOLOGY", ["The clay of the riverbed holds the dye."])[:2] == [
        "clay-0-5cm",
        "soil-ph-0-5cm",
    ]


def test_a_word_inside_another_word_chooses_nothing() -> None:
    assert section_layer_order("GEOLOGY", ["The photograph shows the oregano trade."])[0] == "soil-ph-0-5cm"


def test_without_a_named_subject_the_registry_order_stands() -> None:
    assert section_layer_order("GEOLOGY", []) == [
        "soil-ph-0-5cm",
        "soil-organic-carbon-0-5cm",
        "clay-0-5cm",
        "sand-0-5cm",
        "cation-exchange-0-5cm",
        "elevation",
        "slope",
        "mineral-sites",
    ]
    assert section_layer_order("HISTORY", ["The rain fell."]) == []


def test_the_place_builders_add_to_their_fields() -> None:
    fields = {entry.kind: (entry.disciplines, entry.wait_seconds) for entry in BLOCK_BUILDERS}
    assert fields["region_story"] == ({"GEOGRAPHY"}, 20.0)
    assert fields["map_layer"] == ({"GEOLOGY", "CLIMATE"}, 8.0)


def climate_pipeline(pieces: MemoryPieces, research: FakeResearch | None = None) -> Any:
    entry = next(entry for entry in BLOCK_BUILDERS if entry.kind == "map_layer")
    understand = {**UNDERSTOOD_REPLY, "disciplines": ["CLIMATE"], "seats": ["CLIMATOLOGIST"]}
    answer = pipeline(
        replies=[REPLY, replacements()],
        pieces=pieces,
        research=research,
        understand_model=understanding_model(understand),
    )
    return dataclasses.replace(answer, builders=BlockBuilders([(entry, MapLayerBuilder(place_tools()))]))


def shown_blocks(found: list[tuple[str, dict]]) -> list[tuple[str, str, bool]]:
    return [
        (payload["block"]["id"], payload["block"]["kind"], payload["block"]["reuse"] is not None)
        for name, payload in found
        if name == "block"
    ]


async def test_a_reused_climate_section_still_gets_its_map_layer(offered: dict[str, Any]) -> None:
    pieces = MemoryPieces(views=list(VIEWS), sources=dict(SOURCES))
    first = events(await streamed(asked(), climate_pipeline(pieces)))
    assert shown_blocks(first) == [("s1.b1", "prose", False), ("s1.b2", "map_layer", False)]
    assert [piece.kind for piece in pieces.current()] == ["prose"]
    research = FakeResearch()
    again = events(await streamed(asked(), climate_pipeline(pieces, research)))
    assert research.requests == []
    assert shown_blocks(again) == [("s1.b1", "prose", True), ("s1.b2", "map_layer", False)]
    assert [discipline for _, discipline, _ in offered["asked"]] == ["CLIMATE", "CLIMATE"]
