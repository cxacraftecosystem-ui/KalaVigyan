import asyncio
import re
import uuid
from pathlib import Path

import pytest

from app.core.errors import InvalidInput
from app.models import ClaimSource, Source
from app.research import stream
from app.services import knowledge_view

REPO = Path(__file__).resolve().parents[3]

WIRE = {
    "source": (
        {
            "id",
            "kind",
            "title",
            "authors",
            "year",
            "doi",
            "url",
            "publisher",
            "licence",
            "attribution",
            "reliability",
            "containerTitle",
        },
        {
            "id",
            "kind",
            "title",
            "authors",
            "year",
            "doi",
            "url",
            "publisher",
            "licence",
            "attribution",
            "reliability",
        },
    ),
    "status": ({"step", "message"}, {"step", "message"}),
    "open_question": ({"sectionId", "heading", "sentence"}, {"sectionId", "sentence"}),
    "reaction": (
        {"id", "label", "equation", "balanced", "level", "conditions", "citations"},
        {"id", "label", "equation", "balanced", "level", "conditions", "citations"},
    ),
    "follow_ups": ({"items"}, {"items"}),
    "not_enough_evidence": ({"message"}, {"message"}),
    "done": ({"answerId", "quizAvailable"}, {"answerId"}),
    "error": ({"message"}, {"message"}),
}
CITATION = {"id", "claimId", "sourceId", "quote", "locator", "context", "evidence", "level"}


def schema_of(name: str) -> dict:
    return stream.STREAM_EVENTS[name].json_schema(by_alias=True)


def test_the_event_names_are_the_frontend_set_plus_status_and_the_explainer_events() -> None:
    assert set(stream.STREAM_EVENTS) == {
        "status",
        "not_enough_evidence",
        "source",
        "open_question",
        "reaction",
        "follow_ups",
        "done",
        "error",
        "understood",
        "section_started",
        "section_state",
        "block",
        "section_done",
        "section_heading",
        "lede",
        "trail",
        "paced",
        "builds_on",
        "version",
    }


@pytest.mark.parametrize("name", sorted(WIRE))
def test_each_event_keeps_its_wire_fields(name: str) -> None:
    properties, required = WIRE[name]
    schema = schema_of(name)
    assert set(schema["properties"]) == properties
    assert set(schema.get("required", [])) == required


def test_sentences_and_citations_keep_their_wire_fields() -> None:
    defs = schema_of("open_question")["$defs"]
    assert set(defs["Citation"]["properties"]) == CITATION
    assert set(defs["Citation"]["required"]) == CITATION
    assert set(defs["AnswerSentence"]["properties"]) == {
        "id",
        "text",
        "level",
        "citations",
        "translated",
        "original",
    }
    assert set(defs["AnswerSentence"]["required"]) == {"id", "text", "level", "citations"}
    assert defs["AnswerSentence"]["properties"]["citations"]["minItems"] == 1
    assert defs["Citation"]["properties"]["evidence"]["enum"] == ["QUOTED", "INFERRED"]


def test_frames_are_one_compact_json_line() -> None:
    assert stream.event_frame("done", {"answerId": None}) == 'event: done\ndata: {"answerId":null}\n\n'
    offered = {"answerId": "a1", "quizAvailable": False}
    assert (
        stream.event_frame("done", offered)
        == 'event: done\ndata: {"answerId":"a1","quizAvailable":false}\n\n'
    )
    frame = stream.event_frame("status", stream.StatusEvent(step="COMPOSING", message="Writing °C\nnow"))
    assert frame == 'event: status\ndata: {"step":"COMPOSING","message":"Writing °C\\nnow"}\n\n'


def test_the_wire_refuses_uncited_sentences_and_unknown_events() -> None:
    sentence = {"id": "a", "text": "Alum works.", "level": "PROVISIONAL", "citations": []}
    with pytest.raises(InvalidInput):
        stream.event_frame("open_question", {"sectionId": "open", "sentence": sentence})
    with pytest.raises(InvalidInput):
        stream.event_frame("ping", {})


@pytest.mark.parametrize("name", ["match", "section", "sentence"])
def test_the_retired_events_are_no_longer_on_the_wire(name: str) -> None:
    assert name not in stream.STREAM_EVENTS
    with pytest.raises(InvalidInput):
        stream.event_frame(name, {})


def test_the_retired_resolving_step_is_refused() -> None:
    assert stream.STATUS_STEPS == (
        "PLANNING",
        "SEARCHING_STORED",
        "RESEARCHING",
        "READING",
        "COMPOSING",
        "WRITING_BACK",
        "TRANSLATING",
    )
    with pytest.raises(InvalidInput):
        stream.event_frame("status", {"step": "RESOLVING", "message": "Finding the craft"})


def test_what_the_stored_answer_path_emits_fits_the_contract() -> None:
    source = Source(
        id=uuid.uuid4(),
        kind="BOOK",
        title="Ajrakh",
        authors=[{"name": "A. Author"}, "B. Author"],
        year=2001,
        doi="10.1000/ajrakh",
        url="http://example.org/old",
        publisher=None,
        licence=None,
        attribution=None,
        reliability="B",
    )
    claim_id = uuid.uuid4()
    cite = ClaimSource(id=uuid.uuid4(), claimId=claim_id, sourceId=source.id, quote="alum", locator="p. 2")
    view = knowledge_view.ClaimView(
        claim_id,
        "Alum is the mordant.",
        "PROVISIONAL",
        "MECHANISM",
        None,
        citations=[knowledge_view.citation(cite, "PROVISIONAL")],
    )
    ref = stream.parse_event("source", knowledge_view.source_ref(source))
    assert ref.url == "https://doi.org/10.1000/ajrakh"
    assert stream.parse_event("open_question", {"sectionId": "open", "sentence": view.payload()})


def test_the_heartbeat_beats_every_proxy_timeout() -> None:
    cloudfront = (REPO / "infra" / "terraform" / "cloudfront.tf").read_text(encoding="utf-8")
    nginx = (REPO / "infra" / "terraform" / "user_data.sh").read_text(encoding="utf-8")
    origin_read = int(re.search(r"origin_read_timeout\s*=\s*(\d+)", cloudfront).group(1))
    proxy_read = int(re.search(r"proxy_read_timeout\s+(\d+)s", nginx).group(1))
    assert stream.HEARTBEAT_SECONDS == 60
    assert min(origin_read, proxy_read) > stream.HEARTBEAT_SECONDS
    assert stream.HEARTBEAT_FRAME == ": keep-alive\n\n"


async def test_the_stream_sends_a_heartbeat_while_nothing_else_is_sent() -> None:
    async def produce(emit: stream.Emit) -> None:
        await emit("status", {"step": "RESEARCHING", "message": "Searching 2 live queries"})
        await asyncio.sleep(0.05)
        await emit("done", {"answerId": None})

    frames = [frame async for frame in stream.event_stream(produce, heartbeat_seconds=0.01)]
    assert frames[0] == 'event: status\ndata: {"step":"RESEARCHING","message":"Searching 2 live queries"}\n\n'
    assert frames[-1] == 'event: done\ndata: {"answerId":null}\n\n'
    assert set(frames[1:-1]) == {": keep-alive\n\n"}
    assert len(frames) >= 3


async def test_a_quick_stream_sends_no_heartbeat() -> None:
    async def produce(emit: stream.Emit) -> None:
        await emit("done", {"answerId": None})

    frames = [frame async for frame in stream.event_stream(produce, heartbeat_seconds=5)]
    assert frames == ['event: done\ndata: {"answerId":null}\n\n']


async def test_a_payload_off_the_contract_fails_the_producer_loudly() -> None:
    async def produce(emit: stream.Emit) -> None:
        await emit("status", {"step": "PLANNING"})

    with pytest.raises(InvalidInput):
        _ = [frame async for frame in stream.event_stream(produce)]


async def test_closing_the_stream_cancels_the_work_behind_it() -> None:
    cancelled = asyncio.Event()

    async def produce(emit: stream.Emit) -> None:
        await emit("status", {"step": "PLANNING", "message": "Planning the research on Kutch Ajrakh"})
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            cancelled.set()
            raise

    frames = stream.event_stream(produce)
    assert (await anext(frames)).startswith("event: status")
    await frames.aclose()
    assert cancelled.is_set()
