import asyncio
import json
from typing import Any

from app.core.errors import ExternalFailure
from app.providers.router import RouterError
from app.research.retrieval import KnowledgeHits
from app.services.answer_sections import SECTION_STOPPED_NOTE
from app.services.answering import AnswerAsk, answer_question

from ..composer.fixtures import (
    ALUM_CLAIM_ID,
    PLAN,
    QUESTION,
    pack,
    quote,
    replacements,
    section_reply,
    sentence,
)
from ..planner.fakes import FakeModel
from ..science.golden_process import KUT, PA, RED, golden_records, stage_id
from .fakes import (
    BOOK_ID,
    UNDERSTOOD_REPLY,
    FakeResearch,
    FakeStore,
    SectionModel,
    pipeline,
    streamed,
    understanding_model,
)
from .piece_fakes import MemoryPieces
from .test_answer_flow import LAKE_PAPER, REPLY, events

HISTORY_REPLY = section_reply(
    sentence(
        "Alum is the mordant that binds alizarin to cotton.",
        quote(ALUM_CLAIM_ID, "Alum is the mordant that binds alizarin to cotton"),
    )
)
ANSWER_TEXT = "0b1c2d3e-4f50-4617-8293-a4b5c6d7e8f9"
SEARCHED = (
    "Searched 2 stored claims and 1 stored source passage. Live research ran 2 queries: "
    'T3 "Kutch Ajrakh alum mordant"; T4 "Kutch Ajrakh alizarin lake". Sources searched: crossref, '
    "openalex, semantic_scholar, web. Found 4 items, read 3 documents and recorded 1 failed request."
)


def asked(depth: str = "DETAILED") -> AnswerAsk:
    return AnswerAsk(question=QUESTION, depth=depth)


def two_fields(*disciplines: str) -> FakeModel:
    return understanding_model({**UNDERSTOOD_REPLY, "disciplines": list(disciplines)})


async def test_two_sections_compose_in_parallel_and_stream_in_completion_order() -> None:
    chemistry_waits = asyncio.Event()
    model = SectionModel(
        replies={"The chemistry": [REPLY], "History": [HISTORY_REPLY]},
        gates={"The chemistry": chemistry_waits},
    )
    answer_pipeline = pipeline(understand_model=two_fields("CHEMISTRY", "HISTORY"), compose_model=model)
    found: list[tuple[str, dict[str, Any]]] = []

    async def emit(name: str, payload: Any) -> None:
        found.append((name, json.loads(json.dumps(payload, default=lambda m: m.model_dump(mode="json")))))
        if (name, payload) == ("section_done", {"sectionId": "s2", "state": "READY", "searched": None}):
            chemistry_waits.set()

    await answer_question(asked(), answer_pipeline, emit)
    assert [call["title"] for call in model.calls] == ["The chemistry", "History"]
    assert model.answered == ["History", "The chemistry"]
    milestones = [
        (name, payload.get("id") or payload.get("sectionId"))
        for name, payload in found
        if name in ("section_started", "block", "section_done")
    ]
    assert milestones == [
        ("section_started", "s1"),
        ("section_started", "s2"),
        ("block", "s2"),
        ("section_done", "s2"),
        ("block", "s1"),
        ("section_done", "s1"),
    ]
    sources = [payload["id"] for name, payload in found if name == "source"]
    assert sources.count(str(BOOK_ID)) == 1
    assert found[-1] == ("done", {"answerId": ANSWER_TEXT})


async def test_a_sentence_with_no_stored_claim_is_dropped_alone_and_the_section_shows_the_rest() -> None:
    reply = section_reply(
        sentence(
            "Alum is the mordant that binds alizarin to cotton.",
            quote(ALUM_CLAIM_ID, "Alum is the mordant that binds alizarin to cotton"),
        ),
        sentence(
            "Alizarin forms an insoluble red lake with aluminium ions.",
            quote(LAKE_PAPER, "Alizarin forms an insoluble red lake with aluminium ions"),
        ),
    )
    found = events(await streamed(asked(), pipeline(replies=[reply, replacements()])))
    (prose,) = [data["block"] for name, data in found if name == "block" and data["block"]["kind"] == "prose"]
    assert [s["text"] for s in prose["sentences"]] == ["Alum is the mordant that binds alizarin to cotton."]
    assert ("section_done", {"sectionId": "s1", "state": "READY", "searched": None}) in found
    assert "not_enough_evidence" not in [name for name, _ in found]


async def test_a_section_whose_every_sentence_lacks_a_stored_claim_says_what_it_searched() -> None:
    reply = section_reply(
        sentence(
            "Alizarin forms an insoluble red lake with aluminium ions.",
            quote(LAKE_PAPER, "Alizarin forms an insoluble red lake with aluminium ions"),
        ),
    )
    found = events(await streamed(asked(), pipeline(replies=[reply, replacements()])))
    assert [name for name, _ in found if name == "block"] == []
    assert ("section_done", {"sectionId": "s1", "state": "EMPTY", "searched": SEARCHED}) in found
    message = f"There is not enough cited evidence to answer this about Kutch Ajrakh yet. {SEARCHED}"
    assert found[-2:] == [("not_enough_evidence", {"message": message}), ("done", {"answerId": ANSWER_TEXT})]


async def test_a_process_section_shows_a_ladder_built_from_the_stored_rows() -> None:
    reply = section_reply(stages=[stage_id(RED), stage_id(KUT), "not-a-stage"])
    model = SectionModel(replies={"How it is made": [reply]})
    store = FakeStore(records=golden_records())
    answer_pipeline = pipeline(understand_model=two_fields("PROCESS"), compose_model=model, store=store)
    found = events(await streamed(asked(), answer_pipeline))
    (call,) = model.calls
    offered = call["schema"]["properties"]["stages"]["items"]["enum"]
    assert offered == [str(stage_id(KUT)), str(stage_id(PA)), str(stage_id(RED))]
    assert "process stages stored for the craft" in call["user"]
    (block,) = [payload["block"] for name, payload in found if name == "block"]
    assert (block["id"], block["kind"]) == ("s1.b1", "process_ladder")
    assert [stage["stageId"] for stage in block["stages"]] == [str(stage_id(KUT)), str(stage_id(RED))]
    sent = {payload["id"] for name, payload in found if name == "source"}
    cited = {c["sourceId"] for stage in block["stages"] for s in stage["sentences"] for c in s["citations"]}
    assert cited <= sent
    assert ("section_done", {"sectionId": "s1", "state": "READY", "searched": None}) in found


async def test_stored_claims_that_compose_nothing_send_the_section_to_live_research() -> None:
    plan = PLAN.model_copy(update={"queries": [], "tiers": ["T0", "T1", "T2"], "max_fetches": 0})
    stored_only = pack(plan=plan, evidence=(), documents=())
    research = FakeResearch(packs={"CHEMISTRY": [stored_only]})
    unusable = section_reply(
        sentence("Alum is a mordant.", quote("openalex:W404", "a passage that was never read"))
    )
    model = SectionModel(replies={"The chemistry": [unusable, json.dumps({"sentences": []}), REPLY]})
    held = MemoryPieces(held_fields=("CHEMISTRY",))
    found = events(await streamed(asked(), pipeline(research=research, compose_model=model, pieces=held)))
    first, fresh = research.requests
    assert (first.fresh, fresh.fresh) == (False, True)
    assert (fresh.share.queries, fresh.share.fetches) == (4, 10)
    states = [payload["state"] for name, payload in found if name == "section_state"]
    assert states == ["WRITING", "CHECKING", "RESEARCHING", "WRITING", "CHECKING"]
    (block,) = [payload["block"] for name, payload in found if name == "block"]
    assert [s["id"] for s in block["sentences"]] == ["s1.b1.1", "s1.b1.2", "s1.b1.3"]


async def test_each_section_researches_its_own_field_within_a_share_of_the_depth_budget() -> None:
    research = FakeResearch()
    model = SectionModel(
        replies={"The chemistry": [REPLY], "History": [HISTORY_REPLY], "Climate": [HISTORY_REPLY]}
    )
    disciplines = two_fields("CHEMISTRY", "HISTORY", "CLIMATE")
    await streamed(
        asked("BASIC"), pipeline(research=research, understand_model=disciplines, compose_model=model)
    )
    shares = {r.focus: (r.share.queries, r.share.native_queries, r.share.fetches) for r in research.requests}
    assert shares == {"CHEMISTRY": (1, 0, 2), "HISTORY": (1, 0, 2), "CLIMATE": (0, 0, 1)}
    assert {request.seats for request in research.requests} == {("CHEMIST", "HISTORIAN")}


async def test_a_section_whose_research_fails_ends_empty_while_the_others_answer() -> None:
    class HistoryFails(FakeResearch):
        async def __call__(self, request, progress, trail, *, reads=None):
            if request.focus == "HISTORY":
                raise ExternalFailure("every source failed", kind="unavailable", service="live_research")
            return await super().__call__(request, progress, trail, reads=reads)

    model = SectionModel(replies={"The chemistry": [REPLY]})
    answer_pipeline = pipeline(
        research=HistoryFails(), understand_model=two_fields("CHEMISTRY", "HISTORY"), compose_model=model
    )
    found = events(await streamed(asked(), answer_pipeline))
    assert ("section_done", {"sectionId": "s2", "state": "EMPTY", "searched": SECTION_STOPPED_NOTE}) in found
    assert ("section_done", {"sectionId": "s1", "state": "READY", "searched": None}) in found
    assert found[-1] == ("done", {"answerId": ANSWER_TEXT})


async def test_a_spent_allowance_in_any_section_stops_the_answer_in_its_own_words() -> None:
    allowance = "You have reached today's AI allowance for your role. It resets at midnight IST."
    research = FakeResearch(failure=RouterError("ceiling", allowance, reason="role_daily_cap"))
    found = events(await streamed(asked(), pipeline(research=research)))
    assert found[-2:] == [("error", {"message": allowance}), ("done", {"answerId": None})]


async def test_with_no_stored_or_live_evidence_a_section_composes_nothing() -> None:
    empty = pack(stored=KnowledgeHits(craft_slug="Kutch-Ajrakh"), evidence=(), documents=())
    model = SectionModel(replies={})
    found = events(await streamed(asked(), pipeline(research=FakeResearch(pack=empty), compose_model=model)))
    assert model.calls == []
    assert found[-2][0] == "not_enough_evidence"
