from typing import Any

from app.composer.composer import ModelComposer
from app.research.understanding import Understanding
from app.services.answer_lede import LedeTools, LedeWriting, early_opening, lede_plan
from app.services.explainer_events import ExplainerStream
from app.services.piece_lookup import PieceLookup

from ..planner.fakes import FakeModel, FakeRetriever
from ..research.fixtures import AJRAKH
from .fakes import FakeEnrichment, FakeStore, translation

HINDI = "अजरख में फिटकरी क्यों डालते हैं?"
ROMANISED = "Ajrakh mein phitkari kyun dalte hain?"
RENDERED = "Why is alum added in Ajrakh?"
UNDERSTOOD = {
    "craft": AJRAKH.model_dump(),
    "candidates": [],
    "disciplines": ["CHEMISTRY"],
    "seats": ["CHEMIST"],
    "depth": "DETAILED",
    "language": "hi",
    "basis": "MODEL",
}


async def quiet(name: str, data: Any) -> None:
    return None


def test_the_lede_plan_reads_the_understanding_s_english_rendering_and_else_the_question() -> None:
    rendered = Understanding.model_validate(UNDERSTOOD | {"englishQuestion": RENDERED})
    assert lede_plan(HINDI, rendered, [], PieceLookup()).english == RENDERED
    unrendered = Understanding.model_validate(UNDERSTOOD)
    assert lede_plan(ROMANISED, unrendered, [], PieceLookup()).english == ROMANISED


async def test_a_hindi_question_s_lede_searches_the_one_english_rendering_with_no_translate_call() -> None:
    understanding = Understanding.model_validate(UNDERSTOOD | {"englishQuestion": RENDERED})
    translator = FakeModel([])
    retriever = FakeRetriever()
    tools = LedeTools(compose=ModelComposer(model=FakeModel([])).lede, retriever=retriever)
    writing = LedeWriting(
        ExplainerStream(quiet, language="hi"),
        translation(translator),
        await FakeEnrichment().tools().for_answer(AJRAKH),
    )
    plan = lede_plan(HINDI, understanding, [], PieceLookup())
    opening = await early_opening(plan, tools, writing, FakeStore().cited)
    assert [query.text for query in retriever.queries] == [RENDERED]
    assert (opening.english, opening.deferred, translator.calls) == (RENDERED, True, [])
