import json
import uuid

from app.composer.candidates import compose_request
from app.composer.composer import ModelComposer
from app.composer.prompt import LEDE_SYSTEM_PROMPT, REGENERATE_SYSTEM_PROMPT, lede_schema
from app.research.composition import ComposeCandidate, ComposeFocus, LedeRequest, LedeSection
from app.research.structured import schema_problems

from ..planner.fakes import FakeModel
from ..research.fixtures import AJRAKH
from .fixtures import (
    ALUM_CLAIM_ID,
    ALUM_CLAIM_TEXT,
    QUESTION,
    lede_sentences,
    pack,
    quote,
    replacements,
    section_reply,
    sentence,
)

HARDE_ID = uuid.UUID("4b1c2d3e-0000-4000-8000-00000000b2b2")
HARDE_TEXT = "Harde, a paste of myrobalan, carries the tannin that is an essential pre-mordant."
ALUM = sentence(
    "Alum is the mordant that binds alizarin to cotton.",
    quote(ALUM_CLAIM_ID, "Alum is the mordant that binds alizarin to cotton"),
)
HARDE = sentence(
    "Harde, a myrobalan paste, carries the tannin that is an essential pre-mordant.",
    quote(HARDE_ID, "Harde, a paste of myrobalan, carries the tannin that is an essential pre-mordant"),
)
UNQUOTED = sentence("Alum fixes the red in 3 baths.")


def candidate(claim_id: uuid.UUID, text: str) -> ComposeCandidate:
    return ComposeCandidate(
        id=str(claim_id), kind="CLAIM", text=text, source_label="stored claim", level="PROVISIONAL"
    )


def request(*sections: LedeSection) -> LedeRequest:
    return LedeRequest(
        question=QUESTION,
        craft=AJRAKH,
        candidates=[candidate(ALUM_CLAIM_ID, ALUM_CLAIM_TEXT), candidate(HARDE_ID, HARDE_TEXT)],
        sections=list(sections),
    )


def lede_reply(
    *sentences: dict, headings: list | None = None, follow_ups: list | None = None, answer: int = 0
) -> str:
    return json.dumps(
        {
            "sentences": lede_sentences(*sentences, answer=answer),
            "headings": headings or [],
            "followUps": follow_ups or [],
        }
    )


async def test_the_lede_is_written_from_stored_claims_with_headings_for_the_sections_it_is_shown() -> None:
    chemistry = LedeSection(section_id="s1", discipline="CHEMISTRY", claim_ids=[str(ALUM_CLAIM_ID)])
    headings = [
        {"section": "s1", "heading": "Alum binds the red to cotton"},
        {"section": "s9", "heading": "A section nobody offered"},
        {"section": "s1", "heading": "A second heading for the same section"},
    ]
    model = FakeModel(
        [lede_reply(ALUM, HARDE, headings=headings, follow_ups=["Why does iron spot the cloth?"])]
    )
    composed = await ModelComposer(model=model).lede(request(chemistry))
    (call,) = model.calls
    assert call["system"] == LEDE_SYSTEM_PROMPT and call["schema"] == lede_schema(["s1"])
    assert f"- s1 (chemistry): {ALUM_CLAIM_ID}" in call["user"]
    assert [s.text for s in composed.sentences] == [ALUM["text"], HARDE["text"]]
    assert [s.claim_ids for s in composed.sentences] == [[ALUM_CLAIM_ID], [HARDE_ID]]
    assert composed.headings == {"s1": "Alum binds the red to cotton"}
    assert composed.follow_ups == ["Why does iron spot the cloth?"]


async def test_a_failing_lede_sentence_is_regenerated_once_against_the_same_sources() -> None:
    model = FakeModel([lede_reply(ALUM, UNQUOTED), replacements((0, HARDE))])
    composed = await ModelComposer(model=model).lede(request())
    assert [call["system"] for call in model.calls] == [LEDE_SYSTEM_PROMPT, REGENERATE_SYSTEM_PROMPT]
    assert "Failed sentence 0: UNCITED" in model.calls[1]["user"]
    assert [s.text for s in composed.sentences] == [ALUM["text"], HARDE["text"]]


async def test_a_heading_naming_a_field_or_carrying_a_number_is_not_kept() -> None:
    sections = [
        LedeSection(section_id=f"s{n}", discipline="CHEMISTRY", claim_ids=[str(ALUM_CLAIM_ID)])
        for n in (1, 2, 3)
    ]
    headings = [
        {"section": "s1", "heading": "The chemistry"},
        {"section": "s2", "heading": "Alum in 3 baths"},
        {"section": "s3", "heading": "'Alum binds the red'"},
    ]
    model = FakeModel([lede_reply(ALUM, HARDE, headings=headings)])
    composed = await ModelComposer(model=model).lede(request(*sections))
    assert composed.headings == {"s3": "Alum binds the red"}


async def test_the_sentence_the_model_marks_as_the_answer_opens_the_lede() -> None:
    model = FakeModel([lede_reply(HARDE, ALUM, answer=1)])
    composed = await ModelComposer(model=model).lede(request())
    assert [s.text for s in composed.sentences] == [ALUM["text"], HARDE["text"]]
    assert lede_schema()["properties"]["sentences"]["items"]["properties"]["answer"] == {"type": "boolean"}


async def test_a_lede_whose_answer_sentence_fails_its_checks_has_no_sentences() -> None:
    model = FakeModel([lede_reply(UNQUOTED, ALUM, HARDE), replacements()])
    composed = await ModelComposer(model=model).lede(request())
    assert [call["system"] for call in model.calls] == [LEDE_SYSTEM_PROMPT, REGENERATE_SYSTEM_PROMPT]
    assert composed.sentences == []


async def test_a_lede_reply_marking_no_answer_has_no_sentences() -> None:
    unmarked = json.dumps({"sentences": [ALUM, HARDE], "headings": [], "followUps": []})
    composed = await ModelComposer(model=FakeModel([unmarked])).lede(request())
    assert composed.sentences == []


async def test_no_stored_claim_means_no_lede_call() -> None:
    model = FakeModel([])
    composed = await ModelComposer(model=model).lede(LedeRequest(question=QUESTION, craft=AJRAKH))
    assert (composed.sentences, model.calls) == ([], [])


async def test_a_section_reply_carries_its_own_heading_unless_it_names_the_field() -> None:
    focus = ComposeFocus(discipline="CHEMISTRY", title="The chemistry")
    for heading, kept in (
        ("Alum binds the red to cotton", "Alum binds the red to cotton"),
        ("The Chemistry", None),
    ):
        reply = json.dumps(json.loads(section_reply(ALUM)) | {"heading": heading})
        composed = await ModelComposer(model=FakeModel([reply])).compose(
            compose_request(pack(), QUESTION, focus=focus)
        )
        assert composed.heading == kept
        assert composed.sections[0].heading == "The chemistry"


def test_the_lede_schema_keeps_to_the_portable_keywords() -> None:
    assert schema_problems(lede_schema(["s1", "s2"])) == []
    assert schema_problems(lede_schema()) == []
