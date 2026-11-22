from typing import Any

from app.research.stream import parse_event
from app.services.answer_trail import TrailLog
from app.services.knowledge_view import source_ref
from app.sources.adapter import build_document
from app.sources.scholarly.pacing import AnswerPace, ServicePace

from ..composer.fixtures import ABSTRACT, ABSTRACT_ITEM, packed
from .fakes import BOOK, BOOK_ID


async def test_a_trail_key_only_moves_forward_and_each_frame_keeps_the_contract() -> None:
    sent: list[tuple[str, dict[str, Any]]] = []

    async def emit(name: str, payload: dict[str, Any]) -> None:
        parse_event(name, payload)
        sent.append((name, payload))

    trail = TrailLog(emit)
    document = build_document(ABSTRACT_ITEM, ABSTRACT, "ABSTRACT")
    await trail.found([packed(ABSTRACT_ITEM, "crossref")])
    await trail.read(document)
    await trail.found([packed(ABSTRACT_ITEM, "crossref")])
    await trail.found_stored([source_ref(BOOK)])
    await trail.quoted([ABSTRACT_ITEM.id, "openalex:W404"], [source_ref(BOOK)])
    await trail.quoted([ABSTRACT_ITEM.id], [source_ref(BOOK)])
    assert [(p["key"], p["stage"]) for _, p in sent] == [
        ("crossref:10.1000/lake", "FOUND"),
        ("crossref:10.1000/lake", "READ"),
        (f"source:{BOOK_ID}", "FOUND"),
        ("crossref:10.1000/lake", "QUOTED"),
        (f"source:{BOOK_ID}", "QUOTED"),
    ]
    assert sent[2][1] | {"stage": "FOUND"} == {
        "key": f"source:{BOOK_ID}",
        "stage": "FOUND",
        "group": "STORED",
        "title": "Ajrakh: the printed cloth of Kutch",
        "url": None,
        "publisher": "Mapin",
        "year": 2016,
        "sourceId": str(BOOK_ID),
        "storedAt": None,
    }


async def test_a_long_stored_title_and_publisher_are_cut_to_what_the_contract_accepts() -> None:
    sent: list[dict[str, Any]] = []

    async def emit(name: str, payload: dict[str, Any]) -> None:
        parse_event(name, payload)
        sent.append(payload)

    long = {**source_ref(BOOK), "title": "T" * 1500, "publisher": "P" * 400}
    await TrailLog(emit).found_stored([long])
    (payload,) = sent
    assert (len(payload["title"]), len(payload["publisher"])) == (1000, 300)


async def test_the_waits_for_a_service_s_pace_join_the_trail_once_each_time_they_change() -> None:
    sent: list[tuple[str, dict[str, Any]]] = []
    records = [
        AnswerPace("r1", (ServicePace("crossref", 2.5, 2), ServicePace("arxiv"))),
        AnswerPace("r1", (ServicePace("crossref", 2.5, 2), ServicePace("arxiv"))),
        AnswerPace("r1", (ServicePace("crossref", 3.75, 3), ServicePace("core", unsent=1))),
    ]

    async def emit(name: str, payload: dict[str, Any]) -> None:
        parse_event(name, payload)
        sent.append((name, payload))

    trail = TrailLog(emit, paces=lambda: records.pop(0))
    for _ in range(3):
        await trail.found([packed(ABSTRACT_ITEM, "crossref")])
    paced = [payload for name, payload in sent if name == "paced"]
    assert paced == [
        {
            "services": [
                {"service": "crossref", "waitedSeconds": 2.5, "waitedRequests": 2, "refusals": 0, "unsent": 0}
            ]
        },
        {
            "services": [
                {
                    "service": "crossref",
                    "waitedSeconds": 3.75,
                    "waitedRequests": 3,
                    "refusals": 0,
                    "unsent": 0,
                },
                {"service": "core", "waitedSeconds": 0.0, "waitedRequests": 0, "refusals": 0, "unsent": 1},
            ]
        },
    ]


async def test_an_answer_outside_a_request_records_no_wait() -> None:
    sent: list[str] = []

    async def emit(name: str, payload: dict[str, Any]) -> None:
        sent.append(name)

    await TrailLog(emit, paces=lambda: None).found([packed(ABSTRACT_ITEM, "crossref")])
    assert sent == ["trail"]
