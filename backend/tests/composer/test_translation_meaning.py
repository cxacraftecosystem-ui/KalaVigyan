import json

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.composer.translation import TRANSLATE_SYSTEM_PROMPT, ModelTranslator, translate_schema
from app.composer.translation_meaning import READ_BACK_SYSTEM_PROMPT, ReadBackTranslator
from app.research.translation import TranslationRequest, Translator
from app.services.answer_store import build_answer_translation

from ..planner.fakes import FakeModel

ENGLISH = "Mordant baths held 8 g/L alum and were heated to 60 °C."
HINDI = "मॉर्डेंट के घोल में 8 g/L फिटकरी थी और उसे 60 °C तक गरम किया गया।"
READING = "The mordant bath held 8 g/L alum and was heated to 60 °C."
DRIFTED = "Iron baths held 8 g/L dye and were cooled to 60 °C."
HEADING = "Mordant"
HEADING_HI = "मॉर्डेंट"


def request(language: str = "hi", **texts: str) -> TranslationRequest:
    return TranslationRequest(
        language=language, items=[{"key": key, "text": text} for key, text in texts.items()]
    )


def reply(**texts: str) -> str:
    return json.dumps(
        {"items": [{"key": key, "text": text} for key, text in texts.items()]}, ensure_ascii=False
    )


def checked(model: FakeModel) -> ReadBackTranslator:
    return ReadBackTranslator(translator=ModelTranslator(model=model), model=model)


def test_the_read_back_translator_is_a_translator() -> None:
    assert isinstance(checked(FakeModel([])), Translator)


async def test_a_translation_read_back_with_the_english_meaning_is_kept() -> None:
    model = FakeModel([reply(a=HINDI, h=HEADING_HI), reply(a=READING, h="Mordant")])
    assert await checked(model).translate(request(a=ENGLISH, h=HEADING)) == {"a": HINDI, "h": HEADING_HI}
    forward, reading = model.calls
    assert forward["system"] == TRANSLATE_SYSTEM_PROMPT
    assert reading["system"] == READ_BACK_SYSTEM_PROMPT
    assert reading["schema"] == translate_schema(["a", "h"])
    assert "Target language: English" in reading["user"]
    assert HINDI in reading["user"]
    assert ENGLISH not in reading["user"]


async def test_a_translation_whose_reading_drifted_keeps_its_original() -> None:
    model = FakeModel([reply(a=HINDI, h=HEADING_HI), reply(a=DRIFTED, h="Mordant")])
    assert await checked(model).translate(request(a=ENGLISH, h=HEADING)) == {"h": HEADING_HI}


async def test_a_translation_with_no_reading_keeps_its_original() -> None:
    model = FakeModel([reply(a=HINDI, h=HEADING_HI), reply(h="Mordant")])
    assert await checked(model).translate(request(a=ENGLISH, h=HEADING)) == {"h": HEADING_HI}
    model = FakeModel([reply(a=HINDI), "not json"])
    assert await checked(model).translate(request(a=ENGLISH)) == {}


async def test_a_rendering_into_english_and_a_failed_translation_are_not_read_back() -> None:
    model = FakeModel([reply(question="Which mordant fixes the red?")])
    rendered = await checked(model).translate(request("en", question="लाल रंग कौन सा मॉर्डेंट पक्का करता है?"))
    assert rendered == {"question": "Which mordant fixes the red?"}
    model = FakeModel(["not json", "not json"])
    assert await checked(model).translate(request(a=ENGLISH)) == {}
    assert len(model.calls) == 2


def test_every_answer_translation_is_read_back() -> None:
    translation = build_answer_translation(async_sessionmaker(), model=FakeModel([]))
    assert isinstance(translation.translator, ReadBackTranslator)
