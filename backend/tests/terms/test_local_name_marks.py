from collections.abc import Mapping, Sequence
from typing import Any

from app.research.blocks import ExplainerSentence
from app.research.quiz import quiz_block
from app.research.term_marking import GlossaryEntry, TermMarker
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
TERM_NAMES = {
    "alum": ("Alum", "fatakdi", "फिटकरी"),
    "madder": ("Madder", "मजीठ"),
    "indigo": ("Indigo", "nil", "नील"),
}


class Translator:
    async def translate(self, request: TranslationRequest) -> dict[str, str]:
        return {item.key: HINDI[item.key] for item in request.items if item.key in HINDI}


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


async def hindi(names: Mapping[str, Sequence[str]] | None) -> list[ExplainerSentence]:
    translation = AnswerTranslation(translator=Translator(), cache=NoCache())
    shown = await translated_sentences(
        SENTENCES, language="hi", translation=translation, claim_texts={}, term_names=names
    )
    return [ExplainerSentence.model_validate(sentence) for sentence in shown]


async def test_a_hindi_answer_keeps_its_quiz_on_the_local_names() -> None:
    assert quiz_block([await hindi(None)], block_id="quiz") is None
    quiz = quiz_block([await hindi(TERM_NAMES)], block_id="quiz")
    assert quiz is not None
    assert [(q.prompt, [o.text for o in q.options], q.answer) for q in quiz.questions] == [
        ("_____ लाल रंग को पक्का करती है।", ["नील", "फिटकरी", "मजीठ"], 1),
        ("_____ से लाल रंग मिलता है।", ["नील", "फिटकरी", "मजीठ"], 2),
        ("_____ से नीला रंग मिलता है।", ["नील", "फिटकरी", "मजीठ"], 0),
    ]


def test_a_name_in_an_indian_script_is_marked_only_as_a_whole_word() -> None:
    marker = TermMarker([GlossaryEntry("indigo", ("नील",))])
    assert marker.spans("कपड़ा नीला है।") == []
    assert [span.text for span in marker.spans("कपड़ा नील से रंगा गया।")] == ["नील"]
