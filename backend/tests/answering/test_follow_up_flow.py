import json
import uuid
from typing import Any

from app.research.explainer import Explainer
from app.research.explainer_versions import version_problems
from app.services.answering import AnswerAsk
from app.services.explainer_payload import first_version_mark, version_document
from app.services.follow_ups import FollowUp

from ..composer.fixtures import QUESTION, quote, section_reply, sentence
from ..research.fixtures import AJRAKH
from .fakes import ALUM_CLAIM_ID, ANSWER_ID, WRITTEN_IDS, WRITTEN_LAKE_ID, FakeStore, pipeline, streamed

SECOND_ID = uuid.UUID("5e6f7a8b-9c0d-4e1f-8a2b-3c4d5e6f7a8b")
FOLLOW_UP = "How hot is the alum mordant bath for Kutch Ajrakh?"
LAKE_PAPER = "crossref:10.1000/lake"
ALUM = sentence(
    "Alum is the mordant that binds alizarin to cotton.",
    quote(ALUM_CLAIM_ID, "Alum is the mordant that binds alizarin to cotton"),
)
BATH = sentence(
    "Mordant baths held 8 g/L alum and were heated to 60 °C.",
    quote(LAKE_PAPER, "Mordanting baths of 8 g/L alum were heated to 60 °C"),
)
KUTCH_BATH_TEXT = "Kutch Ajrakh mordant baths held 8 g/L alum and were heated to 60 °C."
KUTCH_BATH = sentence(
    KUTCH_BATH_TEXT, quote(LAKE_PAPER, "Mordanting baths of 8 g/L alum were heated to 60 °C")
)


def events(text: str) -> list[tuple[str, dict[str, Any]]]:
    found = []
    for block in text.split("\n\n"):
        if block:
            name, data = block.split("\n", 1)
            found.append((name.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return found


async def first_version() -> Explainer:
    store = FakeStore()
    ask = AnswerAsk(question=QUESTION, depth="DETAILED", craft_slug=AJRAKH.slug)
    await streamed(ask, pipeline(replies=[section_reply(ALUM)], store=store))
    explainer = store.finished[0]["explainer"]
    assert explainer is not None
    return explainer


def follow_up_of(explainer: Explainer, *facets: str) -> AnswerAsk:
    mark = first_version_mark(
        answer_id=explainer.answer_id, question=explainer.question, created_at=explainer.created_at
    )
    return AnswerAsk(
        question=FOLLOW_UP,
        depth="DETAILED",
        craft_slug=AJRAKH.slug,
        language="en",
        builds_on=FollowUp(base=version_document(mark, explainer), facets=facets),
    )


async def asked_again(ask: AnswerAsk, *items: dict[str, Any]) -> tuple[list[tuple[str, Any]], FakeStore]:
    store = FakeStore(answer_id=SECOND_ID, written={**WRITTEN_IDS, KUTCH_BATH_TEXT: WRITTEN_LAKE_ID})
    text = await streamed(ask, pipeline(replies=[section_reply(*items)], store=store))
    return events(text), store


async def test_a_follow_up_deepens_its_section_after_the_blocks_it_showed() -> None:
    first = await first_version()
    found, _ = await asked_again(follow_up_of(first, "CHEMISTRY"), ALUM, BATH)
    names = [name for name, _ in found]
    assert names[:2] == ["understood", "builds_on"]
    assert found[1][1] == {
        "explainerId": str(ANSWER_ID),
        "version": 1,
        "sections": [{"id": "s1", "order": 1}],
    }
    blocks = [payload["block"] for name, payload in found if name == "block"]
    assert [block["id"] for block in blocks] == ["s1.b2"]
    assert [s["text"] for s in blocks[0]["sentences"]] == [
        "Mordant baths held 8 g/L alum and were heated to 60 °C."
    ]
    assert names[-2:] == ["version", "done"]
    assert found[-2][1]["changes"] == [{"sectionId": "s1", "change": "DEEPENED", "blockIds": ["s1.b2"]}]
    assert found[-1][1] == {"answerId": str(SECOND_ID)}


async def test_a_follow_up_keeps_the_older_version_intact() -> None:
    first = await first_version()
    before = first.model_dump(mode="json", by_alias=True)
    _, store = await asked_again(follow_up_of(first, "CHEMISTRY"), ALUM, BATH)
    (finished,) = store.finished
    merged, mark = finished["explainer"], finished["version"]
    assert first.model_dump(mode="json", by_alias=True) == before
    assert (mark.explainer_id, mark.version, mark.based_on, mark.answer_id) == (ANSWER_ID, 2, 1, SECOND_ID)
    assert version_problems(first, merged, mark.changes) == []
    assert merged.sections[0].blocks[0] == first.sections[0].blocks[0]
    assert [block.id for block in merged.sections[0].blocks] == ["s1.b1", "s1.b2"]
    assert (merged.answer_id, merged.question, merged.understood) == (SECOND_ID, FOLLOW_UP, first.understood)
    assert finished["claim_ids"] == [ALUM_CLAIM_ID, WRITTEN_LAKE_ID]


async def test_a_follow_up_on_a_new_field_adds_a_section_after_the_explainer_s_own() -> None:
    first = await first_version()
    found, store = await asked_again(follow_up_of(first, "HISTORY"), KUTCH_BATH)
    started = [payload for name, payload in found if name == "section_started"]
    assert [(s["id"], s["discipline"], s["order"]) for s in started] == [("s2", "HISTORY", 2)]
    (finished,) = store.finished
    assert [(s.id, s.order) for s in finished["explainer"].sections] == [("s1", 1), ("s2", 2)]
    assert finished["version"].changes[0].model_dump(mode="json", by_alias=True) == {
        "sectionId": "s2",
        "change": "ADDED",
        "blockIds": ["s2.b1"],
    }


async def test_a_follow_up_that_finds_nothing_new_makes_no_version() -> None:
    first = await first_version()
    found, store = await asked_again(follow_up_of(first, "CHEMISTRY"), ALUM)
    names = [name for name, _ in found]
    assert "version" not in names and "block" not in names
    (finished,) = store.finished
    assert (finished["explainer"], finished["version"]) == (None, None)
    assert found[-1] == ("done", {"answerId": str(SECOND_ID)})
