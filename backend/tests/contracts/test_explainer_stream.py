import json
from typing import Any

import pytest

from app.core.errors import InvalidInput
from app.research import stream
from app.research.explainer import EXPLAINER_EVENTS
from app.research.trail import TRAIL_GROUP_OF_SOURCE, TRAIL_GROUPS
from app.research.vocabulary import SourceType

from .explainer_golden import DOCUMENT, STREAM, citations_in, golden_json, stream_events
from .golden import golden_text

EXPLAINER_WIRE = {
    "understood": {"crafts", "candidates", "depth", "language", "basis"},
    "section_started": {"id", "discipline", "title", "original", "order", "state"},
    "section_state": {"sectionId", "state"},
    "block": {"sectionId", "block"},
    "section_done": {"sectionId", "state", "searched"},
    "trail": {"key", "stage", "group", "title", "url", "publisher", "year", "sourceId", "storedAt"},
}
TRAIL = {
    "key": "source:d0f53ee9-4b97-5df7-a367-686957bdb7c8",
    "stage": "FOUND",
    "group": "STORED",
    "title": "Geographical Indications Journal No. 188",
    "url": None,
    "publisher": None,
    "year": 2023,
    "sourceId": "d0f53ee9-4b97-5df7-a367-686957bdb7c8",
    "storedAt": None,
}


def parsed_events() -> list[tuple[str, dict[str, Any]]]:
    return [(name, json.loads(data)) for name, data in stream_events() if name is not None]


@pytest.mark.parametrize("name", sorted(EXPLAINER_WIRE))
def test_each_explainer_event_keeps_its_wire_fields(name: str) -> None:
    assert EXPLAINER_EVENTS[name] is stream.STREAM_EVENTS[name]
    schema = stream.STREAM_EVENTS[name].json_schema(by_alias=True)
    assert set(schema["properties"]) == EXPLAINER_WIRE[name]


def test_every_golden_frame_is_written_byte_for_byte() -> None:
    text = golden_text(STREAM)
    assert text.endswith("\n\n") and "\r" not in text
    rebuilt = "".join(
        stream.HEARTBEAT_FRAME if name is None else stream.event_frame(name, json.loads(data))
        for name, data in stream_events()
    )
    assert rebuilt == text


def test_the_stream_starts_understood_keeps_its_heartbeat_and_ends_done() -> None:
    names = [name for name, _ in stream_events()]
    assert names[0] == "understood" and names[-1] == "done"
    assert names.count(None) == 1
    assert "match" not in names


def test_the_stream_reduces_to_the_golden_explainer() -> None:
    sections: dict[str, dict[str, Any]] = {}
    sent_sources: list[str] = []
    events = parsed_events()
    for name, data in events:
        if name == "section_started":
            sections[data["id"]] = {k: data[k] for k in ("id", "discipline", "title", "order")} | {
                "blocks": []
            }
        elif name == "block":
            cited = {c["sourceId"] for c in citations_in(data["block"])}
            assert cited <= set(sent_sources), "a source is sent before the first block citing it"
            sections[data["sectionId"]]["blocks"].append(data["block"])
        elif name == "section_done":
            sections[data["sectionId"]] |= {"state": data["state"], "searched": data["searched"]}
        elif name == "source":
            sent_sources.append(data["id"])
    document = golden_json(DOCUMENT)
    ordered = sorted(sections.values(), key=lambda s: s["order"])
    assert ordered == document["sections"]
    assert dict(events)["understood"] == document["understood"]
    assert dict(events)["follow_ups"]["items"] == document["followUps"]
    assert dict(events)["done"]["answerId"] == document["answerId"]
    assert sorted(sent_sources) == sorted(source["id"] for source in document["sources"])
    assert len(sent_sources) == len(set(sent_sources))


def test_reused_pieces_stream_first() -> None:
    names = [(name, data) for name, data in parsed_events()]
    first_block = next(data for name, data in names if name == "block")
    assert first_block["block"]["reuse"] is not None
    first_trail = next(data for name, data in names if name == "trail")
    assert first_trail["key"] == f"piece:{first_block['block']['reuse']['pieceId']}"
    assert first_trail["storedAt"] == first_block["block"]["reuse"]["storedAt"]


def test_every_source_type_has_a_trail_group() -> None:
    assert set(TRAIL_GROUP_OF_SOURCE) == set(SourceType.__args__)
    assert set(TRAIL_GROUP_OF_SOURCE.values()) == set(TRAIL_GROUPS) - {"STORED"}


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"group": "PAPERS"}, "STORED exactly when"),
        ({"stage": "READ"}, "never read again"),
        ({"storedAt": "2026-11-12T08:15:00Z"}, "exactly when it is a piece"),
        ({"sourceId": None}, "names its stored source"),
        ({"key": "openalex:W2741809807", "sourceId": None}, "STORED exactly when"),
    ],
)
def test_the_trail_marks_stored_knowledge_as_such(change: dict[str, Any], message: str) -> None:
    stream.parse_event("trail", TRAIL)
    with pytest.raises(InvalidInput, match=message):
        stream.parse_event("trail", TRAIL | change)


def test_a_live_trail_entry_names_its_group() -> None:
    live = TRAIL | {"key": "openalex:W2741809807", "group": "PAPERS", "stage": "READ", "sourceId": None}
    assert stream.parse_event("trail", live).group == "PAPERS"


def test_section_events_carry_working_and_final_states() -> None:
    stream.parse_event("section_state", {"sectionId": "s1", "state": "CHECKING"})
    with pytest.raises(InvalidInput):
        stream.parse_event("section_state", {"sectionId": "s1", "state": "READY"})
    with pytest.raises(InvalidInput, match="exactly when it is EMPTY"):
        stream.parse_event("section_done", {"sectionId": "s1", "state": "EMPTY", "searched": None})
    done = stream.parse_event(
        "section_done", {"sectionId": "s1", "state": "EMPTY", "searched": "Searched 2 queries."}
    )
    assert done.state == "EMPTY"
    with pytest.raises(InvalidInput):
        stream.parse_event(
            "section_started",
            {"id": "open", "discipline": "PROCESS", "title": "x", "order": 1, "state": "RESEARCHING"},
        )


def test_understood_offers_at_most_five_crafts_each_once() -> None:
    craft = {"slug": "Kutch-Ajrakh", "name": "Kutch Ajrakh", "path": "/crafts/Kutch-Ajrakh"}
    anyone = stream.parse_event(
        "understood", {"crafts": [], "candidates": [], "depth": "BASIC", "language": "hi"}
    )
    assert anyone.crafts == []
    with pytest.raises(InvalidInput, match="chosen or offered, once"):
        stream.parse_event(
            "understood", {"crafts": [craft], "candidates": [craft], "depth": "EXPERT", "language": "en"}
        )
    with pytest.raises(InvalidInput):
        stream.parse_event("understood", {"crafts": [], "candidates": [], "depth": "DEEP", "language": "en"})
