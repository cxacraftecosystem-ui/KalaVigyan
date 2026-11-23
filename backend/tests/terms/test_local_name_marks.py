from collections.abc import Collection, Mapping, Sequence
from typing import Any

from app.research.blocks import ExplainerSentence
from app.research.quiz import quiz_block
from app.research.term_marking import GlossaryEntry, TermMarker, local_name_spans
from app.research.translation import TranslationRequest
from app.services.answer_translation import TERM_SEGMENT_PREFIX, AnswerTranslation, translated_sentences

from .test_translated_spans import NoCache

HINDI = {
    "q.1": "फिटकरी लाल रंग को पक्का करती है।",
    "q.2": "मजीठ से लाल रंग मिलता है।",
    "q.3": "नील से नीला रंग मिलता है।",
    f"{TERM_SEGMENT_PREFIX}1": "एलम",
    f"{TERM_SEGMENT_PREFIX}2": "मैडर",
    f"{TERM_SEGMENT_PREFIX}3": "इंडिगो",
}
LOCAL_NAMES = {"alum": ("fatakdi", "फिटकरी"), "madder": ("मजीठ",), "indigo": ("nil", "नील")}


class Translator:
    def __init__(self) -> None:
        self.asked = 0

    async def translate(self, request: TranslationRequest) -> dict[str, str]:
        self.asked += 1
        return {item.key: HINDI[item.key] for item in request.items if item.key in HINDI}


class Names:
    def __init__(self) -> None:
        self.asked: list[set[str]] = []

    async def __call__(self, keys: Collection[str]) -> Mapping[str, Sequence[str]]:
        self.asked.append(set(keys))
        return {key: LOCAL_NAMES[key] for key in keys if key in LOCAL_NAMES}


def english(sentence_id: str, text: str, term: str, claim: str) -> dict[str, Any]:
    cited = {"id": f"cite-{sentence_id}", "claimId": claim, "sourceId": "source-1", "quote": text}
    cited |= {"locator": "p. 1", "context": None, "evidence": "QUOTED", "level": "PROVISIONAL"}
    return {
        "id": sentence_id,
        "text": text,
        "level": "PROVISIONAL",
        "citations": [cited],
        "translated": False,
        "terms": [{"text": term, "termKey": term.casefold()}],
    }


SENTENCES = [
    english("q.1", "Alum fixes the red.", "Alum", "00000000-0000-4000-8000-000000000001"),
    english("q.2", "Madder gives the red.", "Madder", "00000000-0000-4000-8000-000000000002"),
    english("q.3", "Indigo gives the blue.", "Indigo", "00000000-0000-4000-8000-000000000003"),
]


async def hindi(names: Names | None) -> tuple[list[dict[str, Any]], Translator]:
    translator = Translator()
    translation = AnswerTranslation(translator=translator, cache=NoCache(), local_names=names)
    shown = await translated_sentences(SENTENCES, language="hi", translation=translation, claim_texts={})
    return shown, translator


async def test_a_term_whose_rendering_is_not_in_the_translation_is_marked_by_its_local_name() -> None:
    names = Names()
    shown, translator = await hindi(names)
    assert [sentence["terms"] for sentence in shown] == [
        [{"text": "फिटकरी", "termKey": "alum"}],
        [{"text": "मजीठ", "termKey": "madder"}],
        [{"text": "नील", "termKey": "indigo"}],
    ]
    assert (translator.asked, names.asked) == (1, [{"alum", "madder", "indigo"}])


async def test_an_english_answer_reads_no_local_names() -> None:
    names = Names()
    translation = AnswerTranslation(translator=Translator(), cache=NoCache(), local_names=names)
    shown = await translated_sentences(SENTENCES, language="en", translation=translation, claim_texts={})
    assert (shown, names.asked) == (SENTENCES, [])


async def test_a_hindi_answer_keeps_its_quiz_on_the_local_names() -> None:
    without, _ = await hindi(None)
    assert quiz_block([[ExplainerSentence.model_validate(s) for s in without]], block_id="quiz") is None
    shown, _ = await hindi(Names())
    quiz = quiz_block([[ExplainerSentence.model_validate(s) for s in shown]], block_id="quiz")
    assert quiz is not None
    assert [(q.prompt, [o.text for o in q.options], q.answer) for q in quiz.questions] == [
        ("_____ लाल रंग को पक्का करती है।", ["नील", "फिटकरी", "मजीठ"], 1),
        ("_____ से लाल रंग मिलता है।", ["नील", "फिटकरी", "मजीठ"], 2),
        ("_____ से नीला रंग मिलता है।", ["नील", "फिटकरी", "मजीठ"], 0),
    ]


def test_a_local_name_is_a_whole_word_of_its_script() -> None:
    marker = TermMarker([GlossaryEntry("indigo", ("नील",))])
    assert marker.spans("कपड़ा नीला है।") == []
    assert [span.text for span in marker.spans("कपड़ा नील से रंगा गया।")] == ["नील"]
    kept = [{"text": "नील", "termKey": "indigo"}]
    assert local_name_spans(
        "नील और फिटकरी", [*kept, {"text": "Alum", "termKey": "alum"}], kept, LOCAL_NAMES
    ) == [{"text": "फिटकरी", "termKey": "alum"}]
