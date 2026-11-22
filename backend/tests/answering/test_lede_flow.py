import dataclasses
import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

from app.composer.composer import ModelComposer
from app.core.errors import ExternalFailure
from app.research.sections import DISCIPLINE_TITLES, is_facet_label
from app.research.structured import StructuredReply
from app.services.answer_events import cited_claims
from app.services.answer_lede import LedeTools
from app.services.answering import AnswerAsk, AnswerPipeline

from ..composer.fixtures import lede_sentences, quote, section_reply, sentence
from ..planner.fakes import FakeModel
from .fakes import (
    ALUM_CLAIM_ID,
    BOOK,
    SOURCES,
    WRITTEN_IDS,
    WRITTEN_LAKE_ID,
    WRITTEN_WASH_ID,
    FakeStore,
    SectionModel,
    pipeline,
    stored_view,
    streamed,
    understanding_model,
)
from .lede_search import LedeStore, StoredSearch
from .piece_fakes import MemoryPieces
from .test_answer_flow import LAKE_PAPER, events
from .test_piece_reuse_flow import first_answer, memory

MORDANT = "Which mordant fixes the red in Kutch Ajrakh block printing?"
INDIGO = "How does indigo turn blue on Kutch Ajrakh cloth?"
WATER = "How does the water of Kachchh shape Kutch Ajrakh?"
WEB_PAGE = "searxng:https://crafts.example.org/ajrakh"
PROCESS_TEXT = "Kutch Ajrakh's red lake withstood 20 washes."
ALUM_RED_ID = uuid.UUID("4b1c2d3e-0000-4000-8000-00000000a1a1")
HARDE_ID = uuid.UUID("4b1c2d3e-0000-4000-8000-00000000b2b2")
ALUM_RED = stored_view(
    ALUM_RED_ID,
    "Red comes from alum as mordant together with dhaori (tamarisk galls).",
    "PROVISIONAL",
    (
        11,
        BOOK,
        "Red color: This color comes from alum as mordant and dhaori na phool (galls of tamarisk).",
        "p. 12",
    ),
)
HARDE = stored_view(
    HARDE_ID,
    "Harde, a paste of myrobalan, carries the tannin that is an essential pre-mordant for printed mordants.",
    "PROVISIONAL",
    (
        12,
        BOOK,
        "The tannin in the Myroballan penetrates the cotton fibres and is essential pre-mordant",
        "p. 9",
    ),
)
MORDANT_LEDE = json.dumps(
    {
        "sentences": lede_sentences(
            sentence(
                "Alum is the mordant that fixes the red, together with dhaori (tamarisk galls).",
                quote(ALUM_RED_ID, "Red comes from alum as mordant together with dhaori (tamarisk galls)"),
            ),
            sentence(
                "Harde, a myrobalan paste, first gives the cloth the tannin that is an essential pre-mordant.",
                quote(
                    HARDE_ID,
                    "Harde, a paste of myrobalan, carries the tannin that is an essential pre-mordant",
                ),
            ),
        ),
        "headings": [],
        "followUps": ["Why does iron in the water spot harde-treated cloth?", MORDANT],
    }
)
REUSED_LEDE = {
    "sentences": lede_sentences(
        sentence(
            "Alum is the mordant that binds alizarin to cotton in Ajrakh.",
            quote(ALUM_CLAIM_ID, "Alum is the mordant that binds alizarin to cotton"),
        ),
        sentence("The red lake withstood 20 washes.", quote(WRITTEN_WASH_ID, "the lake withstood 20 washes")),
    ),
    "headings": [{"section": "s1", "heading": "Alum binds the red to cotton"}],
}
INDIGO_OPEN = ["Why do the darkest blues need more dips in the vat?", "What feeds the bacteria in the naand?"]
WATER_OPEN = ["Why did the stream at the old village run dry?", "How deep are the wells at Ajrakhpur now?"]
OLD_TEMPLATES = {
    "Which materials does Kutch Ajrakh depend on, and why?",
    "What happens at each step of Kutch Ajrakh?",
    "What is the chemistry or physics behind Kutch Ajrakh?",
}


@dataclass
class QuestionModel:
    replies: Mapping[str, str]
    asked: list[str] = field(default_factory=list)

    async def __call__(self, *, system: str, user: str, schema: Mapping[str, Any]) -> StructuredReply:
        question = next(question for question in self.replies if question in user)
        self.asked.append(question)
        return StructuredReply(text=self.replies[question], degraded=False)


def with_heading(reply: str, heading: str) -> str:
    return json.dumps(json.loads(reply) | {"heading": heading})


def sections_model() -> SectionModel:
    chemistry = section_reply(
        sentence(
            "Alum is the mordant that binds alizarin to cotton.",
            quote(ALUM_CLAIM_ID, "Alum is the mordant that binds alizarin to cotton"),
        ),
        sentence(
            "Mordant baths held 8 g/L alum and were heated to 60 °C.",
            quote(LAKE_PAPER, "Mordanting baths of 8 g/L alum were heated to 60 °C"),
        ),
        follow_ups=["How hot must the alum bath be?"],
    )
    process = section_reply(sentence(PROCESS_TEXT, quote(WEB_PAGE, "the lake withstood 20 washes")))
    return SectionModel(
        replies={
            DISCIPLINE_TITLES["CHEMISTRY"]: [with_heading(chemistry, "Alum binds the red to cotton")],
            DISCIPLINE_TITLES["PROCESS"]: [with_heading(process, "How it is made")],
        }
    )


def lede_pipeline(
    lede_model: Any, *, store: FakeStore | None = None, search: StoredSearch | None = None, **given: Any
) -> AnswerPipeline:
    held = store or LedeStore()
    built = pipeline(store=held, **given)
    lede = LedeTools(compose=ModelComposer(model=lede_model).lede, retriever=search or StoredSearch(held))
    return dataclasses.replace(built, lede=lede)


def mordant_store() -> LedeStore:
    return LedeStore(
        stored=cited_claims([ALUM_RED, HARDE], SOURCES),
        written={**WRITTEN_IDS, PROCESS_TEXT: WRITTEN_WASH_ID},
    )


def understood_as(*disciplines: str) -> Any:
    return understanding_model({"craft": "", "craftNames": [], "disciplines": list(disciplines), "seats": []})


async def mordant_answer(store: FakeStore, search: StoredSearch | None = None) -> list[tuple[str, dict]]:
    built = lede_pipeline(
        FakeModel([MORDANT_LEDE]),
        store=store,
        search=search,
        compose_model=sections_model(),
        understand_model=understood_as("PROCESS", "CHEMISTRY"),
    )
    return events(await streamed(AnswerAsk(question=MORDANT, depth="DETAILED"), built))


def names(found: list[tuple[str, dict]]) -> list[str]:
    return [name for name, _ in found]


async def test_the_mordant_question_opens_with_a_cited_lede_naming_alum_and_myrobalan() -> None:
    store = mordant_store()
    search = StoredSearch(store)
    found = await mordant_answer(store, search)
    order = names(found)
    assert order.index("lede") < order.index("block")
    (lede,) = [data["block"] for name, data in found if name == "lede"]
    assert lede["headline"] == MORDANT
    assert lede["figure"] is None
    texts = " ".join(sentence["text"] for sentence in lede["sentences"])
    assert "alum" in texts.casefold() and "myrobalan" in texts.casefold()
    cited = [{c["claimId"] for c in sentence["citations"]} for sentence in lede["sentences"]]
    assert cited == [{str(ALUM_RED_ID)}, {str(HARDE_ID)}]
    sent = [data["id"] for name, data in found[: order.index("lede")] if name == "source"]
    assert {c["sourceId"] for s in lede["sentences"] for c in s["citations"]} <= set(sent)
    assert [(q.craft_slug, q.text, q.mode, q.limit) for q in search.queries] == [
        ("Kutch-Ajrakh", MORDANT, "HYBRID", 24)
    ]


async def test_sections_are_ordered_by_the_question_and_headed_by_what_they_show() -> None:
    store = mordant_store()
    found = await mordant_answer(store)
    started = [data for name, data in found if name == "section_started"]
    assert [(s["id"], s["discipline"], s["order"]) for s in started] == [
        ("s1", "CHEMISTRY", 1),
        ("s2", "PROCESS", 2),
    ]
    headings = [data for name, data in found if name == "section_heading"]
    assert headings == [{"sectionId": "s1", "title": "Alum binds the red to cotton"}]
    assert order_of(found, "section_heading") < order_of(found, "block")
    (finished,) = store.finished
    explainer = finished["explainer"]
    assert [(s.discipline, s.title) for s in explainer.sections] == [
        ("CHEMISTRY", "Alum binds the red to cotton"),
        ("PROCESS", "How Kutch Ajrakh is made"),
    ]
    assert not any(is_facet_label(section.title) for section in explainer.sections)
    assert explainer.lede is not None and explainer.lede.headline == MORDANT
    assert list(finished["claim_ids"])[:2] == [ALUM_RED_ID, HARDE_ID]
    lede_sources = explainer.lede.cited_source_ids()
    assert [source.id for source in explainer.sources][: len(lede_sources)] == lede_sources


def order_of(found: list[tuple[str, dict]], name: str) -> int:
    return names(found).index(name)


async def test_follow_ups_come_from_what_the_answer_left_open_never_the_question_again() -> None:
    found = await mordant_answer(mordant_store())
    (follow_ups,) = [data["items"] for name, data in found if name == "follow_ups"]
    assert follow_ups == [
        "Why does iron in the water spot harde-treated cloth?",
        "How hot must the alum bath be?",
    ]


async def reused_answer(pieces: MemoryPieces, question: str, model: QuestionModel) -> list[tuple[str, dict]]:
    return events(
        await streamed(AnswerAsk(question=question, depth="DETAILED"), lede_pipeline(model, pieces=pieces))
    )


async def test_indigo_and_water_answers_offer_different_open_questions() -> None:
    pieces = memory()
    await first_answer(pieces)
    model = QuestionModel(
        {
            INDIGO: json.dumps(REUSED_LEDE | {"followUps": INDIGO_OPEN}),
            WATER: json.dumps(REUSED_LEDE | {"followUps": WATER_OPEN}),
        }
    )
    indigo = await reused_answer(pieces, INDIGO, model)
    water = await reused_answer(pieces, WATER, model)
    indigo_items = next(data["items"] for name, data in indigo if name == "follow_ups")
    water_items = next(data["items"] for name, data in water if name == "follow_ups")
    assert (indigo_items, water_items) == (INDIGO_OPEN, WATER_OPEN)
    assert indigo_items != water_items
    assert not (set(indigo_items) | set(water_items)) & OLD_TEMPLATES
    for found in (indigo, water):
        assert order_of(found, "lede") < order_of(found, "section_started") < order_of(found, "block")
        started = next(data for name, data in found if name == "section_started")
        assert started["title"] == "Alum binds the red to cotton"
        trail = next(data for name, data in found if name == "trail")
        assert trail["title"] == "Alum binds the red to cotton"


async def test_a_heading_that_names_a_field_or_states_nothing_of_its_section_is_refused() -> None:
    pieces = memory()
    await first_answer(pieces)
    for heading in ("The chemistry", "Green out of the vat, blue in the air"):
        reply = REUSED_LEDE | {"headings": [{"section": "s1", "heading": heading}], "followUps": []}
        found = await reused_answer(pieces, INDIGO, QuestionModel({INDIGO: json.dumps(reply)}))
        started = next(data for name, data in found if name == "section_started")
        assert started["title"] == "The chemistry behind Kutch Ajrakh"


SECTION_BATH = "Mordant baths held 8 g/L alum and were heated to 60 °C."
LATE_BATH = "Alum baths of 8 g/L were heated to 60 °C to mordant the cloth."


def late_lede(*texts: str) -> str:
    quoted = {
        REUSED_LEDE["sentences"][0]["text"]: quote(
            ALUM_CLAIM_ID, "Alum is the mordant that binds alizarin to cotton"
        ),
        SECTION_BATH: quote(WRITTEN_LAKE_ID, "Mordanting baths of 8 g/L alum were heated to 60 °C"),
        LATE_BATH: quote(WRITTEN_LAKE_ID, "Mordanting baths of 8 g/L alum were heated to 60 °C"),
    }
    return json.dumps(
        {
            "sentences": lede_sentences(*(sentence(text, quoted[text]) for text in texts)),
            "headings": [],
            "followUps": ["Does the lake survive sunlight as well as washing?"],
        }
    )


async def late_answer(reply: str) -> tuple[list[tuple[str, dict]], FakeModel, FakeStore]:
    model = FakeModel([reply])
    store = LedeStore()
    built = lede_pipeline(
        model, store=store, compose_model=sections_model(), understand_model=understood_as("CHEMISTRY")
    )
    found = events(await streamed(AnswerAsk(question=MORDANT, depth="DETAILED"), built))
    return found, model, store


async def test_an_answer_without_stored_findings_gets_its_lede_once_its_sections_are_checked() -> None:
    found, model, store = await late_answer(late_lede(REUSED_LEDE["sentences"][0]["text"], LATE_BATH))
    order = names(found)
    assert order.index("block") < order.index("lede") < order.index("follow_ups")
    assert len(model.calls) == 1
    (finished,) = store.finished
    assert finished["explainer"].lede is not None


async def test_a_late_lede_leaves_out_what_a_section_says_so_the_kept_answer_matches_the_page() -> None:
    reply = late_lede(REUSED_LEDE["sentences"][0]["text"], SECTION_BATH, LATE_BATH)
    found, _, store = await late_answer(reply)
    (lede,) = [data["block"] for name, data in found if name == "lede"]
    assert [s["text"] for s in lede["sentences"]] == [REUSED_LEDE["sentences"][0]["text"], LATE_BATH]
    shown = [s["text"] for name, data in found if name == "block" for s in data["block"]["sentences"]]
    assert SECTION_BATH in shown
    (finished,) = store.finished
    kept = [s.text for block in finished["explainer"].sections[0].blocks for s in block.cited_sentences()]
    assert kept == shown


async def test_a_lede_that_fails_leaves_the_sections_to_open_the_answer() -> None:
    class Failing:
        async def __call__(self, *, system: str, user: str, schema: Mapping[str, Any]) -> StructuredReply:
            raise ExternalFailure("the model is down", service="model")

    store = mordant_store()
    built = lede_pipeline(
        Failing(), store=store, compose_model=sections_model(), understand_model=understood_as("CHEMISTRY")
    )
    found = events(await streamed(AnswerAsk(question=MORDANT, depth="DETAILED"), built))
    assert "lede" not in names(found) and "block" in names(found)
    assert names(found)[-1] == "done" and "error" not in names(found)
    (finished,) = store.finished
    assert finished["explainer"].lede is None
