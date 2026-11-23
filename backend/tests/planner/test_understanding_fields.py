import json
from collections.abc import Sequence
from typing import Any

from app.planner.understanding import ModelUnderstander
from app.planner.understanding_prompt import UNDERSTAND_SYSTEM_PROMPT
from app.research.understanding import UnderstandAsk, Understanding
from app.services.section_fields import SectionFields

from .fakes import FakeModel
from .test_field_seats import Held, resolved
from .test_understanding import READ

GLITCHED = "Why does alum fix madder on cotton?"
HINDI = "फिटकरी कपास पर मजीठ को कैसे पक्का करती है?"
ROMANISED = "Ajrakh mein phitkari kyun dalte hain?"
RENDERED = "Why is alum added in Ajrakh?"
HELD = ("OVERVIEW", "PROCESS", "CHEMISTRY", "MATERIALS", "HISTORY", "SOCIETY")
ONE_FIELD = json.dumps({**READ, "disciplines": ["CHEMISTRY"], "seats": ["CHEMIST"]})
WATER = "How do the water, rivers and climate of Kachchh shape where and when Ajrakh is printed?"
WATER_LISTED = ["GEOGRAPHY", "CLIMATE", "PROCESS", "OVERVIEW", "SOCIETY"]


async def understood(
    reply: str, *, question: str = GLITCHED, depth: str = "DETAILED", held: Sequence[str] = HELD
) -> Understanding:
    understander = ModelUnderstander(model=FakeModel([reply]), resolve=resolved, held=Held(held))
    return await understander.understand(UnderstandAsk(question=question, depth=depth))


def with_reply(**fields: Any) -> str:
    return json.dumps({**READ, **fields})


async def test_a_failed_reply_reads_the_fields_from_the_question_s_words_and_tops_them_up() -> None:
    found = await understood("not json")
    assert found.basis == "RESOLVER"
    assert found.disciplines == ["CHEMISTRY", "MATERIALS", "OVERVIEW", "PROCESS", "HISTORY"]
    assert found.seats == ["CHEMIST"]


async def test_a_reply_with_fewer_fields_than_its_depth_is_topped_up_with_fields_the_craft_holds() -> None:
    assert (await understood(ONE_FIELD)).disciplines == [
        "CHEMISTRY",
        "OVERVIEW",
        "PROCESS",
        "MATERIALS",
        "HISTORY",
    ]
    assert (await understood(ONE_FIELD, depth="BASIC")).disciplines == ["CHEMISTRY", "OVERVIEW", "PROCESS"]
    assert (await understood(ONE_FIELD, depth="EXPERT")).disciplines == ["CHEMISTRY"]


async def test_a_craft_that_holds_nothing_more_leaves_the_fields_the_question_asked() -> None:
    assert (await understood(ONE_FIELD, held=())).disciplines == ["CHEMISTRY"]
    assert (await understood("not json", held=())).disciplines == ["CHEMISTRY", "MATERIALS"]


async def test_the_reply_renders_the_question_in_english_for_the_whole_answer() -> None:
    found = await understood(with_reply(englishQuestion=f"  {RENDERED}  "), question=ROMANISED)
    assert found.english_question == RENDERED
    assert found.model_dump(by_alias=True)["englishQuestion"] == RENDERED
    assert "englishQuestion" in UNDERSTAND_SYSTEM_PROMPT
    unrendered = await understood(with_reply(englishQuestion=""), question=ROMANISED)
    assert (unrendered.english_question, unrendered.basis) == (None, "MODEL")


async def test_fields_a_reply_leaves_out_are_read_from_its_english_rendering() -> None:
    found = await understood(json.dumps({"craft": "", "englishQuestion": GLITCHED}), question=HINDI)
    assert found.disciplines[:2] == ["CHEMISTRY", "MATERIALS"]
    raw = await understood(json.dumps({"craft": ""}), question=HINDI)
    assert raw.disciplines[:2] == ["CHEMISTRY", "OVERVIEW"]


async def test_only_the_fields_the_reply_marks_as_asked_are_asked_and_the_rest_explain_them() -> None:
    found = await understood(
        with_reply(disciplines=WATER_LISTED, asked=["GEOGRAPHY", "CLIMATE"]), question=WATER
    )
    assert (found.disciplines, found.asked) == (WATER_LISTED, ["GEOGRAPHY", "CLIMATE"])
    fields = SectionFields.of(found.asked, (), [])
    assert [fields.sentences_max(field, 8) for field in WATER_LISTED] == [8, 8, 4, 4, 4]
    assert "- asked:" in UNDERSTAND_SYSTEM_PROMPT and "ECOLOGY the pollution" in UNDERSTAND_SYSTEM_PROMPT
    assert (
        "MATERIALS what its objects are made of (metal or alloy, clay, fibre, dye)"
        in UNDERSTAND_SYSTEM_PROMPT
    )


async def test_an_asked_field_the_reply_does_not_list_is_left_out_and_none_marked_leaves_every_one_asked() -> (
    None
):
    marked = await understood(
        with_reply(disciplines=WATER_LISTED, asked=["ECOLOGY", "CLIMATE"]), question=WATER
    )
    assert marked.asked == ["CLIMATE"]
    unmarked = await understood(with_reply(disciplines=WATER_LISTED), question=WATER)
    assert unmarked.asked == WATER_LISTED
