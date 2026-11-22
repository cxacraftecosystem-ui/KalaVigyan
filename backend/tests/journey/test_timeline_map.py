import dataclasses
import json
import re
from typing import Any

import pytest
from pydantic import ValidationError

from app.composer.timeline_map import (
    TimelineChoice,
    choose_timeline,
    timeline_map_schema,
)
from app.core.errors import ExternalFailure
from app.research.blocks_journey import TimelinePoint
from app.research.structured import schema_problems
from app.research.timeline import years_named, years_offered
from app.services import journey_builders
from app.services.block_builders import BLOCK_BUILDERS
from app.services.builder_evidence import fact_sentence
from app.services.journey_builders import TimelineMapBuilder
from app.services.place_register import KnownPoints
from app.services.supply_links import OriginPlace
from app.services.supply_places import named_places
from app.services.timeline_story import timeline_block, timeline_entries, timeline_offer

from ..sources.recorded import WIKIDATA_API, WIKIDATA_SPARQL, Reply, wikidata_adapter
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

SEARCHED = ("fustat", "dhamadka", "ajrakhpur", "sindh", "kutch")
YEARS_LINE = re.compile(r"Years offered for (c\d+): ([^\n]+)")


def recorded_places() -> dict[str, Reply | list[Reply]]:
    return {
        WIKIDATA_API: [Reply(f"wikidata_places_{name}.json") for name in SEARCHED],
        WIKIDATA_SPARQL: Reply("wikidata_place_points_fustat.json"),
    }


def history_ask() -> Any:
    return phase_c_ask(timeline_claims(), discipline="HISTORY", section_id="s4")


def choice(reply: dict[str, Any] | None = None) -> TimelineChoice:
    return TimelineChoice.model_validate(reply or TIMELINE_REPLY)


def offer() -> Any:
    ask = history_ask()
    found = timeline_offer(ask.blocks, ask.cited)
    assert found is not None
    return found


@pytest.fixture
def boundary(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    found = {"rows": {boundary_record().code: boundary_record()}}

    async def records(session: Any, codes: Any) -> Any:
        return found["rows"]

    monkeypatch.setattr(journey_builders, "dataset_records", records)
    return found


async def nothing_known(craft: str | None, names: Any) -> KnownPoints:
    return KnownPoints()


def places_from(adapter: Any) -> Any:
    async def finder() -> Any:
        return adapter

    return finder


def test_the_offer_dates_each_statement_only_by_the_years_its_texts_state() -> None:
    offered = {ref: dict(dated.years) for ref, dated in offer().statements.items()}
    assert offered == {
        "c1": {"y1": (1401, 1500)},
        "c2": {"y1": (1501, 1600), "y2": (1586, 1586)},
        "c3": {"y1": (2001, 2001)},
        "c4": {"y1": (1586, 1586), "y2": (1586, 1631), "y3": (1631, 1631)},
    }


def test_the_timeline_is_the_fixture_s_with_only_fustat_placed() -> None:
    entries = timeline_entries(offer(), choice())
    fustat = OriginPlace(*FUSTAT_POINT)
    block = timeline_block(entries, {"fustat": fustat}, boundary_dataset(), block_id=TIMELINE)
    assert block is not None
    assert block.model_dump(mode="json", by_alias=True) == golden_timeline()


async def test_places_without_coordinates_are_listed_but_not_drawn() -> None:
    adapter, recorder = wikidata_adapter(recorded_places())
    entries = timeline_entries(offer(), choice())
    placed = await named_places(adapter, entries.places())
    assert placed == {"fustat": OriginPlace(*FUSTAT_POINT)}
    block = timeline_block(entries, placed, boundary_dataset(), block_id=TIMELINE)
    shown = [(p.name, p.wikidata_id, p.latitude, p.longitude) for p in block.places]
    assert shown == [
        ("Fustat", *FUSTAT_POINT),
        ("Dhamadka", None, None, None),
        ("Ajrakhpur", None, None, None),
        ("Sindh", None, None, None),
        ("Kutch", None, None, None),
    ]
    searched = [request.url.params.get("search") for request in recorder.requests[:5]]
    assert searched == ["Fustat", "Dhamadka", "Ajrakhpur", "Sindh", "Kutch"]
    assert "VALUES ?item { wd:Q839456 wd:Q37488690 }" in recorder.requests[5].url.params["query"]


async def test_the_builder_draws_the_fixture_s_timeline_from_recorded_wikidata(
    boundary: dict[str, Any],
) -> None:
    model = timeline_model()
    adapter, _ = wikidata_adapter(recorded_places())
    built = await TimelineMapBuilder(
        journey_tools(model), places=places_from(adapter), known=nothing_known
    ).build(history_ask())
    (block,) = built.blocks
    assert block.model_dump(mode="json", by_alias=True) == renamed(golden_timeline(), TIMELINE, "s4.timeline")
    assert built.sources == {}
    (call,) = model.calls
    assert schema_problems(call["schema"]) == []
    assert call["user"].count('label="statement">') == 4
    assert "in the year 1586" in call["user"].split('<untrusted_source ref="c2" label="quote">')[1]
    assert dict(YEARS_LINE.findall(call["user"]))["c4"] == "y1 = 1586; y2 = 1586 to 1631; y3 = 1631"


@pytest.mark.parametrize(
    "point",
    [
        {"statement": "c1", "place": "Fustat", "years": "y2"},
        {"statement": "c3", "place": "Fustat", "years": "y1"},
        {"statement": "c9", "place": "Fustat", "years": "y1"},
        {"statement": "c1", "place": "Cairo", "years": "y1"},
    ],
)
def test_a_point_its_statement_does_not_date_or_place_is_refused(point: dict[str, str]) -> None:
    entries = timeline_entries(offer(), choice({"points": [point], "routes": []}))
    assert entries.points == ()
    assert timeline_block(entries, {}, boundary_dataset(), block_id=TIMELINE) is None


def test_a_date_absent_from_the_sentence_and_its_quotes_is_refused() -> None:
    (fustat, *_) = timeline_claims()
    with pytest.raises(ValidationError, match="not stated"):
        TimelinePoint(place=0, year_from=1586, year_to=1586, sentence=fact_sentence(fustat, "s4.b1.1"))
    undated = fact_sentence(fustat, "s4.b1.1").model_copy(
        update={"text": "Resist-printed fragments from Gujarat were found at Fustat.", "citations": []}
    )
    assert years_named([undated.text]) == set()


@pytest.mark.parametrize(
    "route",
    [
        {"statement": "c1", "start": "Gujarat", "end": "Fustat", "years": "y1"},
        {"statement": "c4", "start": "Kutch", "end": "Sindh", "years": "y2"},
        {"statement": "c4", "start": "Sindh", "end": "Sindh", "years": "y2"},
        {"statement": "c4", "start": "Sindh", "end": "Kutch", "years": "y9"},
    ],
)
def test_a_route_without_a_stated_move_is_refused(route: dict[str, str]) -> None:
    entries = timeline_entries(offer(), choice({"points": [], "routes": [route]}))
    assert entries.routes == ()


def test_each_statement_is_one_point_and_points_run_in_time_order() -> None:
    twice = {"statement": "c1", "place": "Fustat", "years": "y1"}
    entries = timeline_entries(
        offer(), choice({**TIMELINE_REPLY, "points": [*TIMELINE_REPLY["points"], twice]})
    )
    assert [entry.names for entry in entries.points] == [("Fustat",), ("Dhamadka",), ("Ajrakhpur",)]


def test_a_numeral_that_counts_is_not_offered_as_a_year() -> None:
    texts = ["Over 1500 artisans worked in 1947, and 1586 was the year they came."]
    assert (1500, 1500) in years_named(texts)
    assert years_offered(texts) == {(1947, 1947), (1586, 1586)}
    assert years_offered(["Rao Bharmalji I (1586-1631) invited printers"]) == years_named(
        ["Rao Bharmalji I (1586-1631) invited printers"]
    )


def test_a_numeral_before_an_irregular_counted_noun_is_not_offered_as_a_year() -> None:
    texts = ["About 1500 people, 1200 men and 1100 children printed there by 1890."]
    assert {(1500, 1500), (1200, 1200), (1100, 1100)} <= years_named(texts)
    assert years_offered(texts) == {(1890, 1890)}
    assert years_offered(["The workshop opened in 1956 as a cooperative."]) == {(1956, 1956)}


async def test_undated_statements_ask_no_model_and_build_nothing(boundary: dict[str, Any]) -> None:
    (fustat, *_) = timeline_claims()
    quoted = fustat.citations[0].model_copy(
        update={"quote": "Fragments were found at the Fostat excavations."}
    )
    undated = dataclasses.replace(fustat, text="Fragments were found at Fustat.", citations=(quoted,))
    model = timeline_model()
    ask = phase_c_ask([undated], discipline="HISTORY", section_id="s4")
    assert (await TimelineMapBuilder(journey_tools(model)).build(ask)).blocks == ()
    assert model.calls == []


async def test_no_boundary_row_builds_no_timeline(boundary: dict[str, Any]) -> None:
    boundary["rows"] = {}
    model = timeline_model()
    assert (await TimelineMapBuilder(journey_tools(model)).build(history_ask())).blocks == ()
    assert model.calls == []


async def test_a_failed_place_lookup_lists_every_place_without_a_pin(boundary: dict[str, Any]) -> None:
    adapter, _ = wikidata_adapter({WIKIDATA_API: Reply("wikidata_entity_missing.json", status=503)})
    built = await TimelineMapBuilder(journey_tools(), places=places_from(adapter), known=nothing_known).build(
        history_ask()
    )
    (block,) = built.blocks
    assert [place.latitude for place in block.places] == [None] * 5


async def test_a_reply_off_its_schema_is_a_model_failure() -> None:
    with pytest.raises(ExternalFailure, match="off its schema"):
        await choose_timeline(timeline_model({"points": [{"statement": "c1"}]}), offer().brief())
    assert schema_problems(timeline_map_schema()) == []
    assert json.loads(timeline_model().replies[0]) == TIMELINE_REPLY


def test_the_timeline_joins_history_economics_and_geography_sections() -> None:
    (entry,) = [entry for entry in BLOCK_BUILDERS if entry.kind == "timeline_map"]
    assert (entry.disciplines, entry.wait_seconds) == ({"HISTORY", "ECONOMICS", "GEOGRAPHY"}, 30.0)
