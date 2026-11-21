import json
from pathlib import Path

from app.core.errors import ExternalFailure
from app.providers.router import RouterError
from app.research.crafts import CraftResolution
from app.research.retrieval import KnowledgeHits
from app.services import answering
from app.services.answer_events import cited_claims
from app.services.answering import AnswerAsk

from ..composer.fixtures import QUESTION, pack, quote, section_reply, sentence
from ..planner.fakes import FakeModel
from ..research.fixtures import AJRAKH, BAGRU
from .fakes import (
    ALUM_CLAIM_ID,
    ANSWER_ID,
    BOOK_ID,
    GUESS_CLAIM_ID,
    LAKE_ID,
    SOURCES,
    SPENT,
    UNDERSTOOD_REPLY,
    VIEWS,
    WEB_ID,
    WRITTEN_LAKE_ID,
    WRITTEN_WASH_ID,
    FakeResearch,
    FakeStore,
    enriched,
    pipeline,
    resolved,
    streamed,
    understanding_model,
)

REPO = Path(__file__).resolve().parents[3]
LAKE_PAPER = "crossref:10.1000/lake"
WEB_PAGE = "searxng:https://crafts.example.org/ajrakh"
REPLY = section_reply(
    sentence(
        "Alum is the mordant that binds alizarin to cotton.",
        quote(ALUM_CLAIM_ID, "Alum is the mordant that binds alizarin to cotton"),
    ),
    sentence(
        "Mordant baths held 8 g/L alum and were heated to 60 °C.",
        quote(LAKE_PAPER, "Mordanting baths of 8 g/L alum were heated to 60 °C"),
    ),
    sentence(
        "Lime in the wash water may brighten the red.",
        quote(GUESS_CLAIM_ID, "Lime in the wash water may brighten the red"),
    ),
    sentence("The red lake withstood 20 washes.", quote(WEB_PAGE, "the lake withstood 20 washes")),
    follow_ups=["How is the alum bath prepared for Kutch Ajrakh?"],
)


def detailed(**changes: object) -> AnswerAsk:
    fields: dict[str, object] = {"question": QUESTION, "depth": "DETAILED"}
    fields.update(changes)
    return AnswerAsk(**fields)


def events(text: str) -> list[tuple[str, dict]]:
    found = []
    for block in text.split("\n\n"):
        if block:
            name, data = block.split("\n", 1)
            found.append((name.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return found


def ambiguous() -> CraftResolution:
    first, second = resolved(AJRAKH).candidates[0], resolved(BAGRU).candidates[0]
    return CraftResolution(
        status="AMBIGUOUS",
        craft=None,
        candidates=[first.model_copy(update={"score": 0.7}), second.model_copy(update={"score": 0.6})],
        normalised="print",
        script="Latn",
    )


def understood(crafts: list, candidates: list, depth: str = "DETAILED") -> tuple[str, dict]:
    return (
        "understood",
        {
            "crafts": [craft.model_dump() for craft in crafts],
            "candidates": [craft.model_dump() for craft in candidates],
            "depth": depth,
            "language": "en",
        },
    )


async def test_a_researched_answer_streams_the_shared_golden_stream() -> None:
    store = FakeStore()
    enrichment = enriched()
    text = await streamed(detailed(), pipeline(replies=[REPLY], store=store, enrichment=enrichment))
    assert text == (REPO / "shared" / "answer-stream.research.golden.sse").read_text(encoding="utf-8")
    assert enrichment.crafts == [AJRAKH.slug]
    ((ask, understanding),) = store.begun
    assert ask.question == QUESTION
    assert (understanding.basis, understanding.disciplines, understanding.seats) == (
        "MODEL",
        ["CHEMISTRY"],
        ["CHEMIST"],
    )
    ((answer_id, _, _),) = store.kept
    (finished,) = store.finished
    assert answer_id == finished["answer_id"] == ANSWER_ID
    assert [(plan.section_id, plan.discipline) for plan in finished["plans"].sections] == [
        ("s1", "CHEMISTRY")
    ]
    assert finished["claim_ids"] == [ALUM_CLAIM_ID, WRITTEN_LAKE_ID, WRITTEN_WASH_ID, GUESS_CLAIM_ID]
    explainer = finished["explainer"]
    assert [(s.id, s.state, [b.id for b in s.blocks]) for s in explainer.sections] == [
        ("s1", "READY", ["s1.b1", "s1.b2"])
    ]
    assert [source.id for source in explainer.sources] == [str(BOOK_ID), str(LAKE_ID), str(WEB_ID)]
    assert explainer.follow_ups == ["How is the alum bath prepared for Kutch Ajrakh?"]


async def test_research_that_finds_nothing_says_what_was_searched() -> None:
    empty = pack(stored=KnowledgeHits(craft_slug=AJRAKH.slug), evidence=(), documents=())
    research = FakeResearch(pack=empty, steps=(("SEARCHING_STORED", 1), ("RESEARCHING", 2)))
    store = FakeStore()
    text = await streamed(detailed(), pipeline(research=research, store=store))
    assert text == (REPO / "shared" / "answer-stream.not-enough.golden.sse").read_text(encoding="utf-8")
    assert store.kept == []
    (finished,) = store.finished
    assert (finished["claim_ids"], finished["explainer"]) == ([], None)


async def test_expert_questions_plan_deep_and_withhold_the_askers_name() -> None:
    research = FakeResearch()
    ask = detailed(depth="EXPERT", withheld_terms=("Meera Rao",))
    await streamed(ask, pipeline(research=research, replies=[REPLY]))
    (request,) = research.requests
    assert (request.mode, request.depth, request.craft) == ("DEEP", "EXPERT", AJRAKH)
    assert request.withheld_terms == ("Meera Rao",)


async def test_basic_questions_plan_hybrid_at_basic_depth() -> None:
    research = FakeResearch()
    await streamed(detailed(depth="BASIC"), pipeline(research=research, replies=[REPLY]))
    (request,) = research.requests
    assert (request.mode, request.depth) == ("HYBRID", "BASIC")


async def test_a_spent_budget_answers_from_stored_findings_without_research() -> None:
    research = FakeResearch()
    store = FakeStore(stored=cited_claims([VIEWS[0], VIEWS[3]], SOURCES))
    found = events(await streamed(detailed(), pipeline(research=research, store=store, spent=True)))
    assert research.requests == []
    assert [name for name, _ in found] == [
        "understood",
        "status",
        "section_started",
        "source",
        "block",
        "section_done",
        "open_question",
        "follow_ups",
        "done",
    ]
    assert found[0] == understood([AJRAKH], [])
    assert found[1][1] == {"step": "SEARCHING_STORED", "message": "Searching stored findings"}
    assert found[2][1] == {
        "id": "s1",
        "discipline": "MATERIALS",
        "title": "Materials and tools",
        "order": 1,
        "state": "CHECKING",
    }
    block = found[4][1]["block"]
    assert (block["id"], block["kind"], block["sentences"][0]["id"]) == ("s1.b1", "prose", "s1.b1.1")
    assert block["sentences"][0]["citations"][0]["claimId"] == str(ALUM_CLAIM_ID)
    assert found[5][1] == {"sectionId": "s1", "state": "READY", "searched": None}
    assert found[6][1]["sentence"]["id"] == "open.1"
    assert found[-1] == ("done", {"answerId": None})


async def test_a_spent_budget_without_stored_findings_is_not_enough_evidence() -> None:
    found = events(await streamed(detailed(), pipeline(spent=True)))
    name, payload = found[-2]
    assert name == "not_enough_evidence"
    assert payload["message"].startswith(
        "There is not enough cited evidence to answer this about Kutch Ajrakh yet."
    )


async def test_a_spent_budget_for_any_craft_says_so_in_its_own_words() -> None:
    none = CraftResolution(status="NONE", craft=None, candidates=[], normalised="why", script="Latn")
    found = events(await streamed(detailed(), pipeline(resolution=none, spent=True)))
    assert found == [understood([], []), ("error", {"message": SPENT}), ("done", {"answerId": None})]


async def test_an_ambiguous_question_about_no_single_craft_is_answered_for_any_craft_offering_both() -> None:
    research = FakeResearch()
    answer_pipeline = pipeline(resolution=ambiguous(), research=research, replies=[REPLY])
    found = events(await streamed(detailed(question="Which crafts of Gujarat use alum?"), answer_pipeline))
    assert found[0] == understood([], [AJRAKH, BAGRU])
    (request,) = research.requests
    assert request.craft is None
    assert found[-1] == ("done", {"answerId": str(ANSWER_ID)})


async def test_without_a_reply_an_ambiguous_question_proceeds_with_the_best_match() -> None:
    research = FakeResearch()
    answer_pipeline = pipeline(
        resolution=ambiguous(), research=research, replies=[REPLY], understand_model=FakeModel(["not json"])
    )
    found = events(await streamed(detailed(), answer_pipeline))
    assert found[0] == understood([AJRAKH], [BAGRU])
    (request,) = research.requests
    assert request.craft == AJRAKH


async def test_a_failed_reply_still_answers_every_field_the_question_names() -> None:
    research = FakeResearch()
    store = FakeStore()
    answer_pipeline = pipeline(
        research=research, replies=[REPLY, REPLY], store=store, understand_model=FakeModel(["not json"])
    )
    await streamed(detailed(question="Why does alum fix madder on cotton?"), answer_pipeline)
    assert sorted(request.focus or "" for request in research.requests) == ["CHEMISTRY", "MATERIALS"]
    (understanding,) = store.understood
    assert (understanding.basis, understanding.disciplines) == ("RESOLVER", ["CHEMISTRY", "MATERIALS"])
    assert understanding.seats == ["CHEMIST"]


async def test_the_model_may_pick_another_ambiguous_candidate() -> None:
    research = FakeResearch()
    model = understanding_model({**UNDERSTOOD_REPLY, "craft": BAGRU.slug})
    answer_pipeline = pipeline(
        resolution=ambiguous(), research=research, replies=[REPLY], understand_model=model
    )
    found = events(await streamed(detailed(), answer_pipeline))
    assert found[0] == understood([BAGRU], [AJRAKH])
    (request,) = research.requests
    assert request.craft == BAGRU


async def test_a_question_naming_no_known_craft_is_answered_for_any_craft() -> None:
    none = CraftResolution(status="NONE", craft=None, candidates=[], normalised="why", script="Latn")
    research = FakeResearch()
    answer_pipeline = pipeline(resolution=none, research=research, replies=[REPLY])
    found = events(await streamed(detailed(), answer_pipeline))
    assert found[0] == understood([], [])
    assert found[1] == ("status", {"step": "PLANNING", "message": "Planning the research"})
    (request,) = research.requests
    assert request.craft is None
    assert found[-1] == ("done", {"answerId": str(ANSWER_ID)})


async def test_an_unusable_understanding_reply_still_answers_from_the_resolver() -> None:
    research = FakeResearch()
    store = FakeStore()
    answer_pipeline = pipeline(
        research=research, replies=[REPLY], store=store, understand_model=FakeModel(["not json"])
    )
    found = events(await streamed(detailed(), answer_pipeline))
    assert found[0] == understood([AJRAKH], [])
    assert [request.craft for request in research.requests] == [AJRAKH]
    assert store.understood[0].basis == "RESOLVER"


async def test_an_unknown_slug_is_not_found_without_a_match() -> None:
    none = CraftResolution(status="NONE", craft=None, candidates=[], normalised="why", script="Latn")
    found = events(await streamed(detailed(craft_slug="No-Such-Craft"), pipeline(resolution=none)))
    assert found == [("error", {"message": answering.NOT_FOUND_DETAIL}), ("done", {"answerId": None})]


async def test_a_failed_craft_lookup_answers_for_any_craft() -> None:
    failure = ExternalFailure("embedding route timed out", kind="unavailable", service="embeddings")
    research = FakeResearch()
    found = events(
        await streamed(detailed(), pipeline(resolution=failure, research=research, replies=[REPLY]))
    )
    assert found[0] == understood([], [])
    assert [request.craft for request in research.requests] == [None]
    assert "block" in [name for name, _ in found]
    assert found[-1] == ("done", {"answerId": str(ANSWER_ID)})


async def test_a_failed_lookup_of_a_chosen_craft_says_so_without_detail() -> None:
    failure = ExternalFailure("craft index unavailable", kind="unavailable", service="database")
    found = events(await streamed(detailed(craft_slug=AJRAKH.slug), pipeline(resolution=failure)))
    assert found == [
        ("error", {"message": "Finding the craft failed just now. Try again."}),
        ("done", {"answerId": None}),
    ]


async def test_a_spent_allowance_while_finding_the_craft_is_shown_in_its_own_words() -> None:
    allowance = "The daily AI spending ceiling has been reached. Asking resumes at midnight IST."
    failure = RouterError("ceiling", allowance, reason="global_daily_cap")
    found = events(await streamed(detailed(), pipeline(resolution=failure)))
    assert found == [("error", {"message": allowance}), ("done", {"answerId": None})]


async def test_a_spent_allowance_is_shown_in_its_own_words() -> None:
    allowance = "You have reached today's AI allowance for your role. It resets at midnight IST."
    research = FakeResearch(failure=RouterError("ceiling", allowance, reason="role_daily_cap"))
    found = events(await streamed(detailed(), pipeline(research=research)))
    assert found[-2:] == [("error", {"message": allowance}), ("done", {"answerId": None})]


async def test_a_failed_live_research_hides_the_detail() -> None:
    failure = ExternalFailure("every source failed: 503 from api.example", kind="unavailable", service="x")
    found = events(await streamed(detailed(), pipeline(research=FakeResearch(failure=failure))))
    assert found[-2:] == [
        ("error", {"message": answering.RESEARCH_FAILED_DETAIL}),
        ("done", {"answerId": None}),
    ]


async def test_an_unexpected_failure_still_ends_the_stream() -> None:
    found = events(await streamed(detailed(), pipeline(research=FakeResearch(failure=RuntimeError("boom")))))
    assert found[-2:] == [("error", {"message": answering.UNEXPECTED_DETAIL}), ("done", {"answerId": None})]


def test_status_messages_count_in_words() -> None:
    assert answering.status_message("RESEARCHING", 1) == "Searching 1 live query"
    assert answering.status_message("READING", 2) == "Reading the best of 2 sources found"
    assert answering.status_message("PLANNING", craft="Bagru Print") == "Planning the research on Bagru Print"
    assert answering.status_message("PLANNING") == "Planning the research"
