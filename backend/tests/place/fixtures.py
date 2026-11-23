from __future__ import annotations

import json
import uuid
from collections.abc import AsyncIterator, Mapping, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest

from app.geo.river_trace import DistrictHit, ReachLink, districts_in_path_order, river_trace, traced_reach_ids
from app.research.blocks import ExplainerSentence, ProseBlock
from app.research.blocks_place import DistrictRef
from app.research.datasets import DatasetRef
from app.research.piece_reuse import ClaimState
from app.research.planning import PlanRequest
from app.research.rivers import RIVER_NAME_DATASET_CODES, RiverTrace
from app.research.sections import SectionSpec
from app.services import place_builders
from app.services.answer_events import CitedClaims
from app.services.builder_interface import BuildAsk, BuilderTools
from app.services.knowledge_view import ClaimView
from app.services.place_claims import PlaceClaims
from app.services.region_story import LayerOffer, OfferedRiver, RegionOffer

from ..contracts.golden import golden_json
from ..contracts.phase_b_golden import phase_b, phase_b_blocks
from ..planner.fakes import FakeModel
from ..research.fixtures import AJRAKH

KACHCHH = 449
KACHCHH_BASIN = "river.kachchh.golden.json"
OUTLET = 41063203
STORY = "s1.b1"
LAYER = "s2.b1"
GOLDEN_REPLY = {
    "river": "r1",
    "steps": [{"claim": f"c{n}", "district": f"d{KACHCHH}"} for n in range(1, 5)],
    "layers": ["river-density"],
}


def golden_story() -> dict[str, Any]:
    return phase_b_blocks()[STORY]


def golden_layer() -> dict[str, Any]:
    return phase_b_blocks()[LAYER]


def dataset_rows() -> dict[str, DatasetRef]:
    rows = [*golden_story()["datasets"], *golden_layer()["datasets"]]
    return {
        row["code"]: DatasetRef.model_validate(row)
        for row in rows
        if row["code"] not in RIVER_NAME_DATASET_CODES
    }


def fixture_reaches() -> dict[int, ReachLink]:
    reaches = golden_json(KACHCHH_BASIN)["objects"]["reaches"]["geometries"]
    return {
        reach["id"]: ReachLink(
            hyriv_id=reach["id"],
            next_down=reach["properties"]["nextDown"],
            main_riv=OUTLET,
            upland_skm=100.0 * reach["properties"]["ordStra"],
        )
        for reach in reaches
    }


def kachchh_trace() -> RiverTrace:
    links = fixture_reaches()
    path = traced_reach_ids(OUTLET, links, named=golden_story()["river"]["reachIds"])
    hits = [DistrictHit(position=position, district_lgd=KACHCHH, entry=0.0) for position in range(len(path))]
    return river_trace(path, links, districts_in_path_order(hits))


def kachchh_ref() -> DistrictRef:
    return DistrictRef.model_validate(golden_story()["districts"][0])


def kachchh_offer(*, datasets: Mapping[str, DatasetRef] | None = None) -> RegionOffer:
    return RegionOffer(
        craft_districts=(KACHCHH,),
        rivers=(OfferedRiver("r1", kachchh_trace(), 3, 1.2),),
        districts={KACHCHH: kachchh_ref()},
        layers=(
            LayerOffer("soil-ph-0-5cm", "Soil pH, 0-5 cm", "SOILGRIDS_2_0"),
            LayerOffer("river-density", "River density", "HYDRORIVERS_1_0"),
        ),
        datasets=dataset_rows() if datasets is None else datasets,
    )


def step_sentences() -> list[dict[str, Any]]:
    return [step["sentence"] for step in golden_story()["steps"]]


def water_views() -> list[ClaimView]:
    return [
        ClaimView(
            id=uuid.UUID(sentence["citations"][0]["claimId"]),
            text=sentence["text"],
            level=sentence["level"],
            concept_type="PLACE",
            concept_id=None,
            citations=sentence["citations"],
        )
        for sentence in step_sentences()
    ]


def water_prose(section_id: str = "s1") -> ProseBlock:
    sentences = [
        ExplainerSentence.model_validate({**sentence, "id": f"{section_id}.b1.{n}"})
        for n, sentence in enumerate(step_sentences(), start=1)
    ]
    return ProseBlock(id=f"{section_id}.b1", kind="prose", version=1, reuse=None, sentences=sentences)


def cited_water() -> CitedClaims:
    sources = {source["id"]: source for source in phase_b()["sources"]}
    prose = water_prose()
    return CitedClaims(
        views={view.id: view for view in water_views()},
        sources={source_id: sources[source_id] for source_id in prose.cited_source_ids()},
    )


def place_ask(discipline: str = "GEOGRAPHY", *, craft: bool = True, section_id: str = "s1") -> BuildAsk:
    request = PlanRequest(
        question="Why does water matter for Ajrakh in Kutch?", mode="HYBRID", craft=AJRAKH if craft else None
    )
    spec = SectionSpec(id=section_id, discipline=discipline, title="Geography and water", order=1)
    return BuildAsk(uuid.UUID(int=1), spec, request, (water_prose(section_id),), cited_water())


@asynccontextmanager
async def no_session() -> AsyncIterator[None]:
    yield None


def visible(*pieces: Any) -> dict[uuid.UUID, ClaimState]:
    found: dict[uuid.UUID, ClaimState] = {}
    for piece in pieces:
        for citation in piece.payload.citations():
            claim = uuid.UUID(citation.claim_id)
            held = found.get(claim, ClaimState(citation.level, frozenset()))
            found[claim] = ClaimState(citation.level, held.citation_ids | {citation.id})
    return found


@dataclass
class StoryReads:
    stories: list[Any] = field(default_factory=list)
    states: dict[uuid.UUID, Any] = field(default_factory=dict)
    cited: CitedClaims = field(default_factory=CitedClaims)
    place: PlaceClaims = field(default_factory=PlaceClaims)
    asked: list[dict[str, Any]] = field(default_factory=list)


def patch_story_reads(monkeypatch: pytest.MonkeyPatch, reads: StoryReads | None = None) -> StoryReads:
    found = reads or StoryReads()

    async def craft(session: Any, slug: str) -> Any:
        return SimpleNamespace(id=uuid.UUID(int=7), slug=slug)

    async def stories(session: Any, craft: Any, facets: Sequence[str]) -> list[Any]:
        found.asked.append({"stories": list(facets)})
        return list(found.stories)

    async def states(session: Any, pieces: Any, **_kwargs: Any) -> tuple[dict[uuid.UUID, Any], CitedClaims]:
        return found.states, found.cited

    async def place(session: Any, craft: Any, districts: Sequence[DistrictRef], ask: Any) -> PlaceClaims:
        found.asked.append({"districts": [d.district_lgd for d in districts], "held": list(ask.held)})
        return found.place

    for name, fake in (
        ("resolve_craft", craft),
        ("region_story_pieces", stories),
        ("claim_states", states),
        ("district_place_claims", place),
    ):
        monkeypatch.setattr(place_builders, name, fake)
    return found


def story_model(*replies: Mapping[str, Any]) -> FakeModel:
    return FakeModel([json.dumps(reply) for reply in replies or (GOLDEN_REPLY,)])


def place_tools(model: FakeModel | None = None) -> BuilderTools:
    return BuilderTools(sessions=no_session, live=None, plan_model=model or story_model(), compose_model=None)


def expected_story(block_id: str, **changes: Any) -> dict[str, Any]:
    story = golden_story()
    steps = [
        {**step, "sentence": {**step["sentence"], "id": f"{block_id}.{n}"}}
        for n, step in enumerate(story["steps"], start=1)
    ]
    datasets = [row for row in story["datasets"] if row["code"] not in RIVER_NAME_DATASET_CODES]
    river = {**story["river"], "name": None}
    return {**story, "id": block_id, "river": river, "steps": steps, "datasets": datasets, **changes}


def codes(rows: Sequence[Any]) -> list[str]:
    return [row.code for row in rows]
