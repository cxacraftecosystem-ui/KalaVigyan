import dataclasses
import json
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from app.composer.supply_map import SupplyLinkChoice, choose_supply_links, supply_map_schema
from app.core.errors import ExternalFailure
from app.research.knowledge_pieces import PieceSlot, knowledge_piece
from app.research.structured import schema_problems
from app.services import craft_matter as craft_matter_module, season_supply_builders
from app.services.block_builders import BLOCK_BUILDERS, BlockBuilders
from app.services.craft_matter import CraftMatter
from app.services.place_points import OriginPlace, RegisterPoint
from app.services.season_supply_builders import SupplyMapBuilder
from app.services.supply_links import SupplyOffer, supply_links, supply_map_block
from app.services.supply_places import chosen_candidate, context_words, origin_places
from app.sources.reference.wikidata_places import PlaceCandidate

from ..contracts.blocks_golden import SUPPLY_DISTRICT
from ..contracts.golden import golden_json
from ..science.golden_process import golden_records
from ..sources.recorded import WIKIDATA_API, WIKIDATA_SPARQL, Reply, wikidata_adapter
from .fixtures import dataset_rows
from .season_supply_fixtures import (
    GOLDEN_LINKS,
    SUPPLY,
    golden_supply,
    indigo_rows,
    links_model,
    season_tools,
    section_ask,
    supply_claims,
)

STORED_AT = datetime(2026, 11, 17, tzinfo=UTC)
BLOCK_ID = "s6.supply"
SHIKARPUR_SINDH = OriginPlace("Q1250069", 28.0, 68.666666666)
PETHAPUR = OriginPlace("Q2764770", 23.2908, 72.6386)


def recorded_places() -> dict[str, Reply | list[Reply]]:
    return {
        WIKIDATA_API: [
            Reply("wikidata_places_shikarpur.json"),
            Reply("wikidata_places_dhamadka.json"),
            Reply("wikidata_places_pethapur.json"),
        ],
        WIKIDATA_SPARQL: Reply("wikidata_place_points.json"),
    }


def golden_offer() -> SupplyOffer:
    indigo, blocks = supply_claims()
    return SupplyOffer(materials={"m1": indigo_rows(indigo)}, statements={"c1": indigo, "c2": blocks})


def choices(*links: dict[str, str]) -> list[SupplyLinkChoice]:
    return [SupplyLinkChoice.model_validate(link) for link in links or GOLDEN_LINKS["links"]]


def matter() -> CraftMatter:
    indigo, _ = supply_claims()
    return CraftMatter(records=golden_records(), materials=(indigo_rows(indigo),))


@pytest.fixture
def stored(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    found: dict[str, Any] = {"matter": matter()}

    async def load(sessions: Any, craft: Any) -> Any:
        return found["matter"]

    monkeypatch.setattr(craft_matter_module, "craft_matter", load)
    return found


def test_the_fixture_s_supply_map_is_three_stated_origins_none_placed() -> None:
    links = supply_links(golden_offer(), choices(), block_id=SUPPLY)
    block = supply_map_block(links, {}, block_id=SUPPLY)
    assert block is not None
    assert block.model_dump(mode="json", by_alias=True) == golden_supply()


async def test_an_origin_without_coordinates_is_listed_but_not_drawn() -> None:
    adapter, recorder = wikidata_adapter(recorded_places())
    links = supply_links(golden_offer(), choices(), block_id=SUPPLY)
    places = await origin_places(adapter, links)
    assert places == {"shikarpur": SHIKARPUR_SINDH, "pethapur": PETHAPUR}
    block = supply_map_block(links, places, block_id=SUPPLY)
    shown = [(link.origin, link.wikidata_id, link.latitude, link.longitude) for link in block.links]
    assert shown == [
        ("Shikarpur", "Q1250069", 28.0, 68.666666666),
        ("Dhamadka", None, None, None),
        ("Pethapur", "Q2764770", 23.2908, 72.6386),
    ]
    searched = [request.url.params.get("search") for request in recorder.requests[:3]]
    assert searched == ["Shikarpur", "Dhamadka", "Pethapur"]
    assert "VALUES ?item { wd:Q1250069 wd:Q2764770 }" in recorder.requests[3].url.params["query"]


def test_a_namesake_is_chosen_only_by_a_place_its_sentence_names() -> None:
    sindh = PlaceCandidate("Q1250069", "Shikarpur", "city and the capital of Shikarpur District in Sindh")
    gujarat = PlaceCandidate("Q7496551", "Shikarpur", "village in Gujarat, India")
    unnamed = PlaceCandidate("Q60793837", "Shikarpur", None)
    (link, *_) = supply_links(golden_offer(), choices(), block_id=SUPPLY)
    assert context_words(link) == {"Sindh", "Dhamadka", "Blue"}
    assert chosen_candidate([sindh, gujarat, unnamed], context_words(link)) == sindh
    assert chosen_candidate([sindh, gujarat, unnamed], {"Rajasthan"}) is None
    assert chosen_candidate([gujarat], set()) == gujarat
    assert chosen_candidate([], {"Sindh"}) is None


@pytest.mark.parametrize(
    "link",
    [
        {"statement": "c1", "material": "m1", "materialWords": "", "origin": "Bhuj"},
        {"statement": "c9", "material": "m1", "materialWords": "", "origin": "Shikarpur"},
        {"statement": "c1", "material": "m7", "materialWords": "", "origin": "Shikarpur"},
        {"statement": "c2", "material": "none", "materialWords": "Madder", "origin": "Pethapur"},
        {"statement": "c2", "material": "none", "materialWords": "", "origin": "Pethapur"},
        {"statement": "c2", "material": "none", "materialWords": "Pethapur", "origin": "Pethapur"},
        {"statement": "c2", "material": "m1", "materialWords": "", "origin": "Pethapur"},
    ],
)
def test_a_link_its_statement_does_not_state_is_dropped(link: dict[str, str]) -> None:
    assert supply_links(golden_offer(), choices(link), block_id=SUPPLY) == []
    assert supply_map_block([], {}, block_id=SUPPLY) is None


def test_a_stored_material_is_linked_by_its_own_claim_or_a_statement_naming_it() -> None:
    indigo, blocks = supply_claims()
    naming = dataclasses.replace(blocks, text=f"Nil for the vats and {blocks.text}")
    offer = SupplyOffer(materials={"m1": indigo_rows(indigo)}, statements={"c1": indigo, "c2": naming})
    link = {"statement": "c2", "material": "m1", "materialWords": "", "origin": "Pethapur"}
    (kept,) = supply_links(offer, choices(link), block_id=SUPPLY)
    assert (kept.material, kept.origin, kept.material_id) == (
        "Indigo",
        "Pethapur",
        indigo_rows(indigo).material_id,
    )


def test_each_origin_of_a_material_is_listed_once() -> None:
    first = GOLDEN_LINKS["links"][0]
    links = supply_links(golden_offer(), choices(first, {**first, "origin": "shikarpur"}), block_id=SUPPLY)
    assert [link.origin for link in links] == ["Shikarpur"]


async def test_the_model_sees_materials_and_statements_only_inside_untrusted_blocks(stored: Any) -> None:
    model = links_model()
    ask = section_ask(supply_claims(), discipline="MATERIALS", section_id="s6")
    adapter, _ = wikidata_adapter(recorded_places())
    built = await SupplyMapBuilder(season_tools(model), places=_returning(adapter)).build(ask)
    (block,) = built.blocks
    assert [link.origin for link in block.links] == ["Shikarpur", "Dhamadka", "Pethapur"]
    (call,) = model.calls
    assert schema_problems(call["schema"]) == []
    assert call["user"].count('label="statement">') == 2
    assert (
        '<untrusted_source ref="m1" label="material">\nMaterial: Indigo\nAlso called: gali, nil'
        in call["user"]
    )
    assert built.sources == {}


async def test_a_failed_place_lookup_lists_every_origin_without_a_place(stored: Any) -> None:
    adapter, _ = wikidata_adapter({WIKIDATA_API: Reply("wikidata_entity_missing.json", status=503)})
    ask = section_ask(supply_claims(), discipline="MATERIALS", section_id="s6")
    built = await SupplyMapBuilder(season_tools(), places=_returning(adapter)).build(ask)
    (block,) = built.blocks
    assert [(link.origin, link.latitude) for link in block.links] == [
        ("Shikarpur", None),
        ("Dhamadka", None),
        ("Pethapur", None),
    ]


async def test_a_reply_off_its_schema_is_a_model_failure() -> None:
    with pytest.raises(ExternalFailure, match="off its schema"):
        await choose_supply_links(links_model({"links": [{"statement": "c1"}]}), golden_offer().brief())
    assert schema_problems(supply_map_schema()) == []


async def test_the_registry_adds_the_supply_map_with_its_sources(stored: Any) -> None:
    (entry,) = [entry for entry in BLOCK_BUILDERS if entry.kind == "supply_map"]
    adapter, _ = wikidata_adapter(recorded_places())
    ask = section_ask(supply_claims(), discipline="MATERIALS", section_id="s6")
    builder = SupplyMapBuilder(season_tools(), places=_returning(adapter))
    added = await BlockBuilders([(entry, builder)]).added(ask)
    (block,) = added.blocks
    assert (block.kind, block.id) == ("supply_map", BLOCK_ID)
    assert set(block.cited_source_ids()) <= set(ask.cited.sources)


async def test_no_craft_and_no_named_origin_build_nothing(stored: Any) -> None:
    ask = section_ask(supply_claims(), discipline="MATERIALS", section_id="s6", craft=False)
    assert (await SupplyMapBuilder(season_tools()).build(ask)).blocks == ()
    quiet = links_model({"links": []})
    ask = section_ask(supply_claims(), discipline="MATERIALS", section_id="s6")
    assert (await SupplyMapBuilder(season_tools(quiet)).build(ask)).blocks == ()
    assert json.loads(quiet.replies[0]) == {"links": []}


def _returning(adapter: Any) -> Any:
    async def places() -> Any:
        return adapter

    return places


async def test_a_placed_supply_map_is_kept_as_a_piece_with_its_coordinates() -> None:
    adapter, _ = wikidata_adapter(recorded_places())
    links = supply_links(golden_offer(), choices(), block_id=SUPPLY)
    block = supply_map_block(links, await origin_places(adapter, links), block_id=SUPPLY)
    slot = PieceSlot(uuid.UUID(int=7), "MATERIALS", "material:kutch-ajrakh", "EXPERT")
    piece = knowledge_piece(
        block, slot, piece_id=uuid.UUID(int=8), answer_id=uuid.UUID(int=9), created_at=STORED_AT
    )
    assert [(link.origin, link.latitude) for link in piece.payload.links] == [
        ("Shikarpur", 28.0),
        ("Dhamadka", None),
        ("Pethapur", 23.2908),
    ]
    assert piece.source_ids == sorted(block.cited_source_ids())


GANDHINAGAR = RegisterPoint(446, 23.175, 72.689)
TO_GANDHINAGAR = {"statement": "c2", "material": "none", "materialWords": "Blocks", "origin": "Gandhinagar"}


def test_an_origin_the_register_holds_is_pinned_at_its_district_citing_the_boundary_row() -> None:
    (link,) = supply_links(golden_offer(), choices(TO_GANDHINAGAR), block_id="s6.b1")
    boundary = dataset_rows()["DR_DISTRICT_SHAPES"]
    block = supply_map_block([link], {"gandhinagar": GANDHINAGAR}, block_id="s6.b1", boundary=boundary)
    expected = golden_json(SUPPLY_DISTRICT)["sections"][0]["blocks"][0]
    assert block.model_dump(mode="json", by_alias=True) == expected
    unbound = supply_map_block([link], {"gandhinagar": GANDHINAGAR}, block_id="s6.b1")
    assert ([(found.latitude, found.district_lgd) for found in unbound.links], unbound.datasets) == (
        [(None, None)],
        [],
    )


async def test_the_builder_places_register_districts_itself_and_asks_wikidata_for_the_rest(
    stored: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    asked: list[set[str]] = []

    async def registered(session: Any, names: Any) -> dict[str, RegisterPoint]:
        asked.append(set(names))
        return {"gandhinagar": GANDHINAGAR}

    async def records(session: Any, codes: Any) -> dict[str, Any]:
        return {"DR_DISTRICT_SHAPES": SimpleNamespace(code="DR_DISTRICT_SHAPES")}

    monkeypatch.setattr(season_supply_builders, "register_points", registered)
    monkeypatch.setattr(season_supply_builders, "dataset_records", records)
    monkeypatch.setattr(season_supply_builders, "region_dataset", lambda record: dataset_rows()[record.code])
    searched: list[list[str]] = []

    async def wikidata(finder: Any, links: Any) -> dict[str, OriginPlace]:
        searched.append([link.origin for link in links])
        return {"pethapur": PETHAPUR}

    monkeypatch.setattr(season_supply_builders, "origin_places", wikidata)
    model = links_model({"links": [*GOLDEN_LINKS["links"], TO_GANDHINAGAR]})
    ask = section_ask(supply_claims(), discipline="MATERIALS", section_id="s6")
    (block,) = (await SupplyMapBuilder(season_tools(model), places=_returning(None)).build(ask)).blocks
    shown = [(link.origin, link.wikidata_id, link.district_lgd) for link in block.links]
    assert shown == [
        ("Shikarpur", None, None),
        ("Dhamadka", None, None),
        ("Pethapur", "Q2764770", None),
        ("Gandhinagar", None, 446),
    ]
    assert asked == [{"Shikarpur", "Dhamadka", "Pethapur", "Gandhinagar"}]
    assert searched == [["Shikarpur", "Dhamadka", "Pethapur"]]
    assert [row.code for row in block.datasets] == ["DR_DISTRICT_SHAPES"]
