from app.research.terms import shown_as_word, spans_still_shown
from app.research.translation import TranslationRequest
from app.services.answer_translation import TERM_SEGMENT_PREFIX, AnswerTranslation, translated_block

from .test_translated_spans import NoCache

ALUM_HI = "फिटकरी से रंग पक्का होता है।"


def span(text: str, key: str) -> dict[str, str]:
    return {"text": text, "termKey": key}


def test_a_word_ends_where_no_letter_mark_or_digit_follows_in_any_script() -> None:
    assert shown_as_word("कुट, गच और साज", "कुट")
    assert not shown_as_word("कुटाई होती है", "कुट")
    assert not shown_as_word("साज़ का पेड़", "साज")
    assert not shown_as_word("ठीक", "ठी")
    assert shown_as_word("(कुट)", "कुट")
    assert not shown_as_word("गच", "कुट")


def test_a_rendering_inside_a_longer_word_marks_nothing() -> None:
    indigo = [span("indigo", "indigo")]
    assert spans_still_shown("कपड़ा नीला है।", indigo, {"indigo": "नील"}) == []
    assert spans_still_shown("कपड़ा नील में रंगा गया।", indigo, {"indigo": "नील"}) == [span("नील", "indigo")]


def test_a_glossary_name_marks_the_term_the_translation_rendered_its_own_way() -> None:
    alum = [span("alum", "alum")]
    names = {"alum": ("alum", "fatakdi", "फिटकरी")}
    assert spans_still_shown(ALUM_HI, alum, {"alum": "एलम"}, names) == [span("फिटकरी", "alum")]
    assert spans_still_shown(ALUM_HI, alum, {"alum": "एलम"}) == []
    assert spans_still_shown(ALUM_HI, alum, {}, {"kut": ("फिटकरी",)}) == []


class AlumTranslator:
    async def translate(self, request: TranslationRequest) -> dict[str, str]:
        replies = {"s1.b1.1": ALUM_HI, f"{TERM_SEGMENT_PREFIX}1": "एलम"}
        return {item.key: replies[item.key] for item in request.items if item.key in replies}


async def test_a_translated_block_marks_the_glossary_s_own_name_of_a_term() -> None:
    sentence = {
        "id": "s1.b1.1",
        "text": "Alum fixes the colour.",
        "level": "PROVISIONAL",
        "citations": [],
        "terms": [span("Alum", "alum")],
    }
    block = {"id": "s1.b1", "kind": "prose", "version": 1, "reuse": None, "sentences": [sentence]}
    translation = AnswerTranslation(translator=AlumTranslator(), cache=NoCache())
    names = {"alum": ("alum", "फिटकरी")}
    shown = await translated_block(
        block, language="hi", translation=translation, claim_texts={}, term_names=names
    )
    plain = await translated_block(block, language="hi", translation=translation, claim_texts={})
    assert shown["sentences"][0]["terms"] == [span("फिटकरी", "alum")]
    assert plain["sentences"][0]["terms"] == []
