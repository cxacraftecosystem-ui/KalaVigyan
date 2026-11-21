import json
from typing import Any

from app.providers.router import RouterError
from app.services.answer_events import cited_claims
from app.services.answer_translation import translated_sentences
from app.services.answering import AnswerAsk

from ..composer.fixtures import QUESTION
from ..planner.fakes import FakeModel
from .fakes import (
    ALUM_CLAIM_ID,
    GUESS_CLAIM_ID,
    SOURCES,
    VIEWS,
    WRITTEN_LAKE_ID,
    WRITTEN_WASH_ID,
    FakeResearch,
    FakeStore,
    MemoryCache,
    pipeline,
    streamed,
    translation,
)
from .test_answer_flow import REPLY, events

ALUM_HI = "फिटकरी वह मॉर्डेंट है जो अजरख में एलिज़रिन को कपास से बाँधती है।"
LIME_HI = "धोने के पानी में चूना लाल रंग को चमका सकता है।"
ALUM_SHORT_HI = "फिटकरी वह मॉर्डेंट है जो एलिज़रिन को कपास से बाँधती है।"
LAKE_HI = "मॉर्डेंट के घोल में 8 g/L फिटकरी थी और उसे 60 °C तक गरम किया गया।"
WASH_HI = "लाल लेक 20 धुलाइयों तक टिकी रही।"
WASH_WITHOUT_NUMBER_HI = "लाल लेक कई धुलाइयों तक टिकी रही।"
CHEMISTRY_HI = "रसायन"
FOLLOW_UP_HI = "कच्छ अजरख के लिए फिटकरी का घोल कैसे तैयार किया जाता है?"
TRANSLATING = {"step": "TRANSLATING", "message": "Translating the answer into Hindi"}


def reply(**texts: str) -> str:
    return json.dumps(
        {"items": [{"key": key, "text": text} for key, text in texts.items()]}, ensure_ascii=False
    )


def verified(question: str = QUESTION) -> AnswerAsk:
    return AnswerAsk(question=question, depth="BASIC", language="hi")


def stored() -> FakeStore:
    return FakeStore(stored=cited_claims([VIEWS[0], VIEWS[3]], SOURCES))


def payloads(found: list[tuple[str, dict]], name: str) -> list[dict[str, Any]]:
    return [payload for event, payload in found if event == name]


def schema_keys(call: dict[str, Any]) -> list[str]:
    return call["schema"]["properties"]["items"]["items"]["properties"]["key"]["enum"]


def block_sentences(found: list[tuple[str, dict]]) -> list[dict[str, Any]]:
    return [sentence for payload in payloads(found, "block") for sentence in payload["block"]["sentences"]]


async def test_a_verified_answer_in_hindi_translates_each_block_and_keeps_its_citations() -> None:
    model = FakeModel([reply(**{"s1.b1.1": ALUM_HI}), reply(**{"open.1": LIME_HI})])
    found = events(
        await streamed(verified(), pipeline(store=stored(), translated=translation(model), spent=True))
    )
    assert TRANSLATING in payloads(found, "status")
    (sentence,) = block_sentences(found)
    assert sentence["text"] == ALUM_HI
    assert sentence["translated"] is True
    assert sentence["original"] == "Alum is the mordant that binds alizarin to cotton in Ajrakh."
    assert sentence["citations"] == VIEWS[0].citations
    (guess,) = payloads(found, "open_question")
    assert (guess["sentence"]["text"], guess["sentence"]["original"]) == (
        LIME_HI,
        "Lime in the wash water may brighten the red.",
    )
    assert guess["sentence"]["citations"] == VIEWS[3].citations
    assert [payload["title"] for payload in payloads(found, "section_started")] == ["Materials and tools"]
    assert [schema_keys(call) for call in model.calls] == [["s1.b1.1"], ["open.1"]]


async def test_cached_claim_translations_make_no_second_model_call() -> None:
    model = FakeModel([reply(**{"s1.b1.1": ALUM_HI}), reply(**{"open.1": LIME_HI})])
    cache = MemoryCache()
    first = events(
        await streamed(verified(), pipeline(store=stored(), translated=translation(model, cache), spent=True))
    )
    second = events(
        await streamed(verified(), pipeline(store=stored(), translated=translation(model, cache), spent=True))
    )
    assert len(model.calls) == 2
    assert sorted(cache.rows) == sorted([(ALUM_CLAIM_ID, "hi"), (GUESS_CLAIM_ID, "hi")])
    assert [sentence["text"] for sentence in block_sentences(second)] == [ALUM_HI]
    assert payloads(first, "block") == payloads(second, "block")


async def test_a_question_in_devanagari_searches_stored_claims_in_english() -> None:
    model = FakeModel(
        [
            reply(question="Why does alum keep Ajrakh red?"),
            reply(**{"s1.b1.1": ALUM_HI}),
            reply(**{"open.1": LIME_HI}),
        ]
    )
    store = stored()
    await streamed(
        verified("अजरख को फिटकरी लाल क्यों रखती है?"),
        pipeline(store=store, translated=translation(model), spent=True),
    )
    assert store.questions == ["Why does alum keep Ajrakh red?"]
    assert schema_keys(model.calls[0]) == ["question"]
    assert model.calls[0]["user"].startswith("Target language: English (en")


async def test_an_english_question_in_verified_mode_makes_no_model_call() -> None:
    model = FakeModel([])
    store = stored()
    ask = AnswerAsk(question=QUESTION, depth="BASIC")
    found = events(await streamed(ask, pipeline(store=store, translated=translation(model), spent=True)))
    assert model.calls == []
    assert (store.questions, store.modes) == ([QUESTION], ["VERIFIED"])
    assert "translated" not in block_sentences(found)[0]


async def test_a_researched_answer_in_hindi_translates_the_title_each_block_and_the_follow_ups() -> None:
    english = events(
        await streamed(AnswerAsk(question=QUESTION, depth="DETAILED"), pipeline(replies=[REPLY]))
    )
    model = FakeModel(
        [
            reply(s1=CHEMISTRY_HI),
            reply(**{"s1.b1.1": ALUM_SHORT_HI, "s1.b1.2": LAKE_HI, "s1.b1.3": WASH_HI}),
            reply(**{"s1.open.1": LIME_HI}),
            reply(**{"follow-up:0": FOLLOW_UP_HI}),
        ]
    )
    cache = MemoryCache()
    research = FakeResearch()
    ask = AnswerAsk(question=QUESTION, depth="DETAILED", language="hi")
    found = events(
        await streamed(
            ask, pipeline(research=research, replies=[REPLY], translated=translation(model, cache))
        )
    )
    assert [schema_keys(call) for call in model.calls] == [
        ["s1"],
        ["s1.b1.1", "s1.b1.2", "s1.b1.3"],
        ["s1.open.1"],
        ["follow-up:0"],
    ]
    (started,) = payloads(found, "section_started")
    assert (started["title"], started["original"]) == (CHEMISTRY_HI, "The chemistry behind Kutch Ajrakh")
    assert [sentence["text"] for sentence in block_sentences(found)] == [ALUM_SHORT_HI, LAKE_HI, WASH_HI]
    assert [s["citations"] for s in block_sentences(found)] == [
        s["citations"] for s in block_sentences(english)
    ]
    assert all(sentence["translated"] for sentence in block_sentences(found))
    assert payloads(found, "follow_ups") == [{"items": [FOLLOW_UP_HI]}]
    assert sorted(cache.rows) == sorted(
        [(WRITTEN_LAKE_ID, "hi"), (WRITTEN_WASH_ID, "hi"), (GUESS_CLAIM_ID, "hi")]
    )
    (request,) = research.requests
    assert (request.language, request.english_question) == ("hi", None)


async def test_a_sentence_failing_its_check_twice_is_shown_in_english() -> None:
    model = FakeModel(
        [
            reply(s1=CHEMISTRY_HI),
            reply(**{"s1.b1.1": ALUM_SHORT_HI, "s1.b1.2": LAKE_HI, "s1.b1.3": WASH_WITHOUT_NUMBER_HI}),
            reply(**{"s1.b1.3": WASH_WITHOUT_NUMBER_HI}),
            reply(**{"s1.open.1": LIME_HI}),
            reply(**{"follow-up:0": FOLLOW_UP_HI}),
        ]
    )
    ask = AnswerAsk(question=QUESTION, depth="DETAILED", language="hi")
    found = events(await streamed(ask, pipeline(replies=[REPLY], translated=translation(model))))
    assert schema_keys(model.calls[2]) == ["s1.b1.3"]
    wash = block_sentences(found)[2]
    assert wash["text"] == "The red lake withstood 20 washes."
    assert "translated" not in wash and "original" not in wash


async def test_a_question_in_tamil_script_no_call_could_render_plans_without_an_english_rendering() -> None:
    research = FakeResearch()
    ask = AnswerAsk(question="அஜ்ரக் ஏன் சிவப்பாக இருக்கிறது?", depth="DETAILED", language="ta")
    model = FakeModel([reply()] * 20)
    found = events(
        await streamed(ask, pipeline(research=research, replies=[REPLY], translated=translation(model)))
    )
    (request,) = research.requests
    assert (request.language, request.english_question) == ("ta", None)
    assert schema_keys(model.calls[0]) == schema_keys(model.calls[1]) == ["question"]
    assert "error" not in [name for name, _ in found]


async def test_a_failed_translation_route_shows_the_answer_in_english() -> None:
    class NoRoute:
        async def __call__(self, **_: object) -> object:
            raise RouterError("no_route", "No enabled route can run TRANSLATE")

    found = events(
        await streamed(verified(), pipeline(store=stored(), translated=translation(NoRoute()), spent=True))
    )
    assert [name for name, _ in found if name == "error"] == []
    (sentence,) = block_sentences(found)
    assert sentence["text"] == "Alum is the mordant that binds alizarin to cotton in Ajrakh."


async def test_voice_sentences_translate_through_the_same_cache() -> None:
    cache = MemoryCache()
    model = FakeModel([reply(**{str(ALUM_CLAIM_ID): ALUM_HI})])
    sentence = {**VIEWS[0].payload(), "id": str(ALUM_CLAIM_ID)}
    texts = {view.id: view.text for view in VIEWS}
    spoken = await translated_sentences(
        [sentence], language="hi", translation=translation(model, cache), claim_texts=texts
    )
    assert spoken == [{**sentence, "text": ALUM_HI, "translated": True, "original": VIEWS[0].text}]
    again = await translated_sentences(
        [sentence], language="hi", translation=translation(model, cache), claim_texts=texts
    )
    assert again == spoken
    assert len(model.calls) == 1
