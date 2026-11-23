from collections.abc import Collection
from typing import Any

import pytest
from pydantic import ValidationError

from app.composer.timeline_map import TimelineChoice
from app.research.blocks_journey import TimelineMapBlock
from app.services import journey_builders
from app.services.journey_builders import TimelineMapBuilder
from app.services.place_points import OriginPlace, RegisterPoint
from app.services.place_register import KnownPoints, register_district
from app.services.timeline_story import timeline_block, timeline_entries, timeline_offer

from ..contracts.blocks_golden import TIMELINE_UNDATED, BlocksFixture
from ..contracts.golden import golden_json, reproduces
from ..place.season_supply_fixtures import claims_of, written_claim
from .fixtures import (
    FUSTAT_POINT,
    TIMELINE,
    TIMELINE_REPLY,
    boundary_dataset,
    boundary_record,
    golden_timeline,
    journey_tools,
    phase_c_ask,
    renamed,
    timeline_claims,
    timeline_model,
)

KACHCHH = RegisterPoint(449, 23.25, 69.67)
DHAMADKA = "Block printers once worked at Dhamadka on the Saran river."
BARMER = "Ajrakh is also printed in Barmer."


def undated_claims() -> list[Any]:
    return [
        written_claim("dhamadka-undated", DHAMADKA, "printers once worked at Dhamadka on the Saran river"),
        written_claim("barmer-undated", BARMER, "Ajrakh is also printed in Barmer"),
    ]


def test_a_place_is_a_register_district_only_when_its_name_is_one_district() -> None:
    assert (register_district("Kutch"), register_district("Kachchh"), register_district("Barmer")) == (
        449,
        449,
        90,
    )
    assert (register_district("Kutch, Gujarat"), register_district("Sindh"), register_district("Fustat")) == (
        None,
        None,
        None,
    )


def test_a_place_the_register_names_is_pinned_at_its_district_in_version_2() -> None:
    offer = timeline_offer(*_history())
    assert offer is not None and offer.undated == ()
    places = {"fustat": OriginPlace(*FUSTAT_POINT), "kutch": KACHCHH}
    block = timeline_block(timeline_entries(offer, _choice()), places, boundary_dataset(), block_id=TIMELINE)
    assert block is not None and block.version == 2
    shown = block.model_dump(mode="json", by_alias=True)
    kutch = {"name": "Kutch", "wikidataId": None, "latitude": 23.25, "longitude": 69.67, "districtLgd": 449}
    golden = golden_timeline()
    assert shown["places"] == [kutch if p["name"] == "Kutch" else p for p in golden["places"]]
    assert {**shown, "version": 1, "places": golden["places"]} == golden


def test_undated_history_sentences_are_listed_with_the_place_they_name() -> None:
    offer = timeline_offer(*_history(undated_claims()))
    assert offer is not None and [claim.text for claim in offer.undated] == [DHAMADKA, BARMER]
    block = timeline_block(timeline_entries(offer, _choice()), {}, boundary_dataset(), block_id=TIMELINE)
    assert block is not None and block.version == 2
    names = [place.name for place in block.places]
    assert names[-1] == "Barmer" and len(names) == len(golden_timeline()["places"]) + 1
    shown = [
        (names[entry.place] if entry.place is not None else None, entry.sentence.id)
        for entry in block.undated
    ]
    assert shown == [("Dhamadka", f"{TIMELINE}.5"), ("Barmer", f"{TIMELINE}.6")]
    assert [entry.sentence.text for entry in block.undated] == [DHAMADKA, BARMER]


def test_version_1_carries_no_undated_sentence_and_no_register_place() -> None:
    golden = golden_timeline()
    sentence = {**golden["points"][0]["sentence"], "id": f"{TIMELINE}.9"}
    with pytest.raises(ValidationError, match="from version 2"):
        TimelineMapBlock.model_validate({**golden, "undated": [{"place": None, "sentence": sentence}]})
    assert TimelineMapBlock.model_validate({**golden, "version": 2}).undated == []


async def test_the_builder_places_register_and_curated_names_before_asking_wikidata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def records(session: Any, codes: Any) -> Any:
        return {boundary_record().code: boundary_record()}

    monkeypatch.setattr(journey_builders, "dataset_records", records)
    asked: list[list[str]] = []

    async def known(craft: str | None, names: Collection[str]) -> KnownPoints:
        asked.append(sorted(names))
        return KnownPoints(register={"kutch": KACHCHH}, curated={"fustat": OriginPlace(*FUSTAT_POINT)})

    finder = NoCandidates()

    async def wikidata() -> NoCandidates:
        return finder

    builder = TimelineMapBuilder(journey_tools(timeline_model()), places=wikidata, known=known)
    (block,) = (
        await builder.build(phase_c_ask(timeline_claims(), discipline="HISTORY", section_id="s4"))
    ).blocks
    assert asked == [["Ajrakhpur", "Dhamadka", "Fustat", "Kutch", "Sindh"]]
    assert finder.searched == ["Dhamadka", "Ajrakhpur", "Sindh"]
    placed = {place.name: (place.wikidata_id, place.district_lgd) for place in block.places if place.latitude}
    assert placed == {"Fustat": (FUSTAT_POINT[0], None), "Kutch": (None, 449)}
    assert block.version == 2 and block.id == "s4.timeline"
    assert renamed(golden_timeline(), TIMELINE, "s4.timeline")["points"] == [
        point.model_dump(mode="json", by_alias=True) for point in block.points
    ]


def _history(extra: list[Any] | None = None) -> tuple[Any, Any]:
    ask = phase_c_ask([*timeline_claims(), *(extra or [])], discipline="HISTORY", section_id="s4")
    return ask.blocks, ask.cited


def _choice() -> TimelineChoice:
    return TimelineChoice.model_validate(TIMELINE_REPLY)


class NoCandidates:
    def __init__(self) -> None:
        self.searched: list[str] = []

    async def place_candidates(self, name: str) -> list[Any]:
        self.searched.append(name)
        return []

    async def place_points(self, item_ids: Any) -> dict[str, Any]:
        return {}


def test_the_version_2_fixture_is_the_builder_s_timeline_with_its_undated_sentence_and_register_place() -> (
    None
):
    assert reproduces(BlocksFixture, TIMELINE_UNDATED)
    (section,) = golden_json(TIMELINE_UNDATED)["sections"]
    (golden,) = section["blocks"]
    undated = claims_of([entry["sentence"] for entry in golden["undated"]])
    offer = timeline_offer(*_history(undated))
    assert offer is not None
    places = {"fustat": OriginPlace(*FUSTAT_POINT), "kutch": KACHCHH}
    block = timeline_block(timeline_entries(offer, _choice()), places, boundary_dataset(), block_id=TIMELINE)
    assert block is not None and block.model_dump(mode="json", by_alias=True) == golden
