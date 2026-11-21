import dataclasses
from dataclasses import dataclass, field
from typing import Any

from app.composer.composer import ModelComposer
from app.providers.router import RouterError
from app.research.planning import PlanRequest
from app.services.answer_catalogue import NO_CATALOGUE, SectionCatalogue
from app.services.answer_lede import LedeTools
from app.services.answering import AnswerAsk, AnswerPipeline

from ..composer.fixtures import QUESTION
from ..planner.fakes import FakeModel
from .fakes import (
    UNDERSTOOD_REPLY,
    FakeResearch,
    FakeStore,
    pipeline,
    streamed,
    translation,
    understanding_model,
)
from .test_answer_flow import REPLY, events
from .test_translation_flow import reply, schema_keys, stored

HINDI = "अजरख में फिटकरी क्यों डालते हैं?"
ROMANISED = "Ajrakh mein phitkari kyun dalte hain?"
RENDERED = "Why is alum added in Ajrakh?"
QUIET = 30


@dataclass
class Catalogue:
    asked: list[str | None] = field(default_factory=list)

    async def __call__(self, request: PlanRequest, discipline: str) -> SectionCatalogue:
        self.asked.append(request.english_question)
        return NO_CATALOGUE


@dataclass
class Asked:
    research: FakeResearch = field(default_factory=FakeResearch)
    store: FakeStore = field(default_factory=FakeStore)
    catalogue: Catalogue = field(default_factory=Catalogue)
    translator: FakeModel = field(default_factory=lambda: FakeModel([reply()] * QUIET))
    found: list[tuple[str, dict]] = field(default_factory=list)

    def pipeline(self, understood: dict[str, Any]) -> AnswerPipeline:
        built = pipeline(
            research=self.research,
            replies=[REPLY],
            store=self.store,
            translated=translation(self.translator),
            understand_model=understanding_model(understood),
        )
        lede = LedeTools(compose=ModelComposer(model=FakeModel([])).lede)
        return dataclasses.replace(built, lede=lede, catalogue=self.catalogue)

    def renderings(self) -> int:
        return sum(1 for call in self.translator.calls if schema_keys(call) == ["question"])


async def asked(
    question: str, understood: dict[str, Any], *, language: str | None = None, **given: Any
) -> Asked:
    run = Asked(**given)
    ask = AnswerAsk(question=question, depth="DETAILED", language=language)
    run.found.extend(events(await streamed(ask, run.pipeline(understood))))
    assert "error" not in [name for name, _ in run.found]
    return run


async def test_every_search_of_a_hindi_question_reads_the_understanding_s_one_english_rendering() -> None:
    run = await asked(HINDI, {**UNDERSTOOD_REPLY, "englishQuestion": RENDERED}, language="hi")
    (request,) = run.research.requests
    assert request.english_question == RENDERED
    assert run.catalogue.asked == [RENDERED]
    assert run.store.questions == [RENDERED]
    assert run.renderings() == 0
    assert run.store.understood[0].english_question == RENDERED


async def test_a_reply_without_a_rendering_has_the_question_rendered_once_for_the_whole_answer() -> None:
    translator = FakeModel([reply(question=RENDERED), *[reply()] * QUIET])
    run = await asked(HINDI, UNDERSTOOD_REPLY, language="hi", translator=translator)
    assert schema_keys(translator.calls[0]) == ["question"]
    assert run.renderings() == 1
    (request,) = run.research.requests
    assert request.english_question == RENDERED
    assert run.store.questions == [RENDERED]


async def test_a_romanised_hindi_question_searches_the_model_s_english_not_its_own_words() -> None:
    run = await asked(ROMANISED, {**UNDERSTOOD_REPLY, "englishQuestion": RENDERED})
    (request,) = run.research.requests
    assert (request.english_question, run.catalogue.asked) == (RENDERED, [RENDERED])


async def test_without_a_rendering_the_raw_words_stand_for_english_only_in_an_english_answer() -> None:
    in_hindi = await asked(ROMANISED, UNDERSTOOD_REPLY, language="hi")
    assert in_hindi.research.requests[0].english_question is None
    in_english = await asked(ROMANISED, UNDERSTOOD_REPLY)
    assert in_english.research.requests[0].english_question == ROMANISED
    plain = await asked(QUESTION, UNDERSTOOD_REPLY)
    assert plain.research.requests[0].english_question == QUESTION


class NoRoute:
    async def __call__(self, **_: object) -> object:
        raise RouterError("ceiling", "The monthly AI budget has been reached.", reason="MONTHLY_CEILING")


async def test_a_refused_budget_with_an_unrendered_question_never_streams_unranked_findings() -> None:
    store = stored()
    ask = AnswerAsk(question=HINDI, depth="BASIC", language="hi")
    found = events(await streamed(ask, pipeline(store=store, translated=translation(NoRoute()), spent=True)))
    assert [name for name, _ in found] == ["understood", "status", "not_enough_evidence", "done"]
    assert store.questions == []
