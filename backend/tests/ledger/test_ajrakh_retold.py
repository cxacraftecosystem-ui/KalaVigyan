from typing import Any

from pydantic import TypeAdapter

from app.research.explainer import Block
from app.services.claim_ledger import ClaimLedger
from app.services.restatements import restates, said

from ..contracts.phase_c_golden import phase_c, phase_c_blocks
from .indigo_blocks import prose

BLOCK = TypeAdapter(Block)
REFS = {ref["id"]: ref for ref in phase_c()["sources"]}
SOURCE = "96fcec75-0cb1-5e32-8e43-f1f1ca5c940c"
PASSAGE = (
    "Indigo is transformed to leucoindigo by the action of indigo-reducing bacteria (indigo → leucoindigo) "
    "{figure}. Although indigo is not soluble in water, leucoindigo is soluble in water."
)
CHEMISTRY = "Indigo does not dissolve in water, but leucoindigo does, and indigo-reducing bacteria turn indigo into leucoindigo."
MATERIALS = "Indigo is not soluble in water, whereas leucoindigo is soluble in water."


def cited(sentence_id: str, text: str, claim: str, quote: str) -> dict[str, Any]:
    citation = {"claimId": claim, "sourceId": SOURCE, "quote": quote}
    return {"id": sentence_id, "text": text, "citations": [citation]}


def test_a_materials_sentence_on_the_chemistry_section_s_passage_restates_it() -> None:
    earlier = cited("s1.b1.1", CHEMISTRY, "512daf80", PASSAGE.format(figure="(Figure 1)"))
    later = cited("s3.b1.1", MATERIALS, "a5761723", PASSAGE.format(figure="( Figure 1 )"))
    assert restates(said(later), said(earlier))


def test_a_sentence_of_the_same_passage_about_something_else_is_still_said() -> None:
    earlier = cited("s1.b1.1", CHEMISTRY, "512daf80", PASSAGE.format(figure="(Figure 1)"))
    other = "Bacteria in the fermentation fluid reduce indigo, but not in cold weather."
    assert not restates(said(cited("s3.b1.1", other, "7a51f227", PASSAGE.format(figure=""))), said(earlier))


def retold(sentence: dict[str, Any], n: int) -> dict[str, Any]:
    text = sentence["text"].removesuffix(".")
    return {**sentence, "id": f"s4.b0.{n}", "text": f"{text}, as the records tell.", "terms": []}


def test_a_timeline_whose_every_entry_the_prose_already_said_is_left_out() -> None:
    timeline = phase_c_blocks()["s4.b1"]
    sentences = [
        *(point["sentence"] for point in timeline["points"]),
        *(r["sentence"] for r in timeline["routes"]),
    ]
    told = prose("s4.b0", ("placeholder", ()))
    told["sentences"] = [retold(sentence, n) for n, sentence in enumerate(sentences, start=1)]
    ledger = ClaimLedger()
    (shown,) = ledger.admit("s4", [BLOCK.validate_python(told)], REFS)
    assert len(list(shown.cited_sentences())) == len(sentences)
    assert ledger.admit("s4", [BLOCK.validate_python(timeline)], REFS) == []
    assert [block.kind for block in ClaimLedger().admit("s4", [BLOCK.validate_python(timeline)], REFS)] == [
        "timeline_map"
    ]
