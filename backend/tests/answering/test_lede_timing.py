import asyncio
import dataclasses
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from app.composer.composer import ModelComposer
from app.core.errors import ExternalFailure
from app.research.evidence_pack import EvidencePack, ResearchTrail
from app.research.planning import PlanRequest
from app.research.stream import ResearchProgress
from app.research.structured import StructuredReply
from app.services.answer_lede import LedeTools
from app.services.answering import AnswerAsk

from ..planner.fakes import FakeModel
from .fakes import (
    UNDERSTOOD_REPLY,
    FakeResearch,
    SectionModel,
    pipeline,
    streamed,
    understanding_model,
)
from .lede_search import StoredSearch
from .test_answer_flow import events
from .test_lede_flow import (
    MORDANT,
    MORDANT_LEDE,
    REUSED_LEDE,
    lede_pipeline,
    mordant_store,
    names,
    sections_model,
    understood_as,
)
from .test_piece_reuse_flow import HISTORY_REPLY, asked, first_answer, memory

SHORT_WAIT = 0.2


@dataclass
class FailingFirst:
    replies: list[str]
    calls: int = 0

    async def __call__(self, *, system: str, user: str, schema: Mapping[str, Any]) -> StructuredReply:
        self.calls += 1
        if self.calls == 1:
            raise ExternalFailure("the model is down", service="model")
        return StructuredReply(text=self.replies.pop(0), degraded=False)


@dataclass
class GatedModel:
    gate: asyncio.Event
    reply: str
    calls: int = 0

    async def __call__(self, *, system: str, user: str, schema: Mapping[str, Any]) -> StructuredReply:
        self.calls += 1
        await self.gate.wait()
        return StructuredReply(text=self.reply, degraded=False)


@dataclass
class SignalledResearch(FakeResearch):
    started: asyncio.Event = field(default_factory=asyncio.Event)

    async def __call__(
        self, request: PlanRequest, progress: ResearchProgress, trail: ResearchTrail
    ) -> EvidencePack:
        self.started.set()
        return await super().__call__(request, progress, trail)


def waiting(built: Any, seconds: float) -> Any:
    return dataclasses.replace(built, lede=dataclasses.replace(built.lede, wait_seconds=seconds))


async def mordant_events(built: Any) -> list[tuple[str, dict]]:
    return events(await streamed(AnswerAsk(question=MORDANT, depth="DETAILED"), built))


async def test_an_early_lede_that_fails_beside_stored_findings_is_not_tried_again() -> None:
    model = FailingFirst([MORDANT_LEDE])
    store = mordant_store()
    built = lede_pipeline(
        model, store=store, compose_model=sections_model(), understand_model=understood_as("CHEMISTRY")
    )
    found = await mordant_events(built)
    assert "lede" not in names(found) and "block" in names(found)
    assert model.calls == 1
    (finished,) = store.finished
    assert finished["explainer"].lede is None


async def test_a_lede_slower_than_its_wait_releases_the_blocks_and_is_never_sent() -> None:
    gate = asyncio.Event()
    model = GatedModel(gate, MORDANT_LEDE)
    store = mordant_store()
    built = lede_pipeline(
        model, store=store, compose_model=sections_model(), understand_model=understood_as("CHEMISTRY")
    )
    found = await asyncio.wait_for(mordant_events(waiting(built, SHORT_WAIT)), timeout=10)
    assert "lede" not in names(found) and "block" in names(found)
    assert names(found)[-1] == "done" and "error" not in names(found)
    assert model.calls == 1
    (finished,) = store.finished
    assert finished["explainer"].lede is None


async def test_the_lede_s_wait_covers_its_stored_read_too() -> None:
    model = FakeModel([MORDANT_LEDE])
    store = mordant_store()
    built = lede_pipeline(
        model,
        store=store,
        search=StoredSearch(store, delay=30),
        compose_model=sections_model(),
        understand_model=understood_as("CHEMISTRY"),
    )
    found = await asyncio.wait_for(mordant_events(waiting(built, SHORT_WAIT)), timeout=10)
    assert "lede" not in names(found) and "block" in names(found)
    assert model.calls == []


async def test_sections_without_a_stored_piece_research_while_the_lede_is_written() -> None:
    pieces = memory()
    await first_answer(pieces)
    research = SignalledResearch()
    lede_model = GatedModel(research.started, json.dumps(REUSED_LEDE | {"followUps": []}))
    two_fields = understanding_model({**UNDERSTOOD_REPLY, "disciplines": ["CHEMISTRY", "HISTORY"]})
    built = pipeline(
        research=research,
        understand_model=two_fields,
        compose_model=SectionModel(replies={"History": [HISTORY_REPLY]}),
        pieces=pieces,
    )
    built = dataclasses.replace(
        built, lede=LedeTools(compose=ModelComposer(model=lede_model).lede, wait_seconds=5)
    )
    found = events(await asyncio.wait_for(streamed(asked(), built), timeout=10))
    order = names(found)
    assert "lede" in order and order.index("lede") < order.index("block")
    started = [(data["id"], data["state"]) for name, data in found if name == "section_started"]
    assert started == [("s2", "RESEARCHING"), ("s1", "WRITING")]
    assert order.index("section_started") < order.index("lede")
