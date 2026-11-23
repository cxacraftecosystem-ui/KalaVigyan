from app.research.explainer import Explainer

from .explainer_golden import DOCUMENT, golden_json
from .golden import reproduces

TRANSLATED = "explainer.translated.golden.json"


def test_the_translated_explainer_is_reproduced_byte_for_byte() -> None:
    assert reproduces(Explainer, TRANSLATED)


def test_a_translated_sentence_keeps_the_english_it_was_translated_from_with_its_citations() -> None:
    english = golden_json(DOCUMENT)["sections"][1]
    explainer = Explainer.model_validate(golden_json(TRANSLATED))
    (section,) = explainer.sections
    assert (explainer.understood.language, section.original) == ("hi", english["title"])
    (prose,) = section.blocks
    (written,) = english["blocks"]
    shown = [
        (s.translated, s.original or s.text, [c.id for c in s.citations]) for s in prose.cited_sentences()
    ]
    assert shown == [
        (n < 2, sentence["text"], [citation["id"] for citation in sentence["citations"]])
        for n, sentence in enumerate(written["sentences"])
    ]
    assert all(s.text != s.original for s in prose.cited_sentences() if s.translated)
