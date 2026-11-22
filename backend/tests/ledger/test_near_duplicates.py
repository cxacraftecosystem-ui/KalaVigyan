from typing import Any

from pydantic import TypeAdapter

from app.research.explainer import Block
from app.services.claim_ledger import ClaimLedger

from .indigo_blocks import block
from .indigo_claims import EDWARDS, FRATER_BOOK, IJTK, KHAMIR_ART, SOURCES, uid

BLOCK = TypeAdapter(Block)
REFS = {ref["id"]: ref for ref in SOURCES}


def cited(sentence_id: str, text: str, claim: str, source: dict[str, Any], quote: str) -> dict[str, Any]:
    citation = {
        "id": uid(f"citation/{claim}"),
        "claimId": uid(f"claim/{claim}"),
        "sourceId": source["id"],
        "quote": quote,
        "locator": None,
        "context": None,
        "evidence": "QUOTED",
        "level": "PROVISIONAL",
    }
    return {"id": sentence_id, "text": text, "level": "PROVISIONAL", "citations": [citation], "terms": []}


def told(ledger: ClaimLedger, section: str, *sentences: dict[str, Any]) -> list[str]:
    said = BLOCK.validate_python(block(f"{section}.b1", "prose", sentences=list(sentences)))
    return [
        sentence.text for shown in ledger.admit(section, [said], REFS) for sentence in shown.cited_sentences()
    ]


def test_the_gazetteer_figures_told_again_under_history_are_said_once() -> None:
    economics = "The 1971 Gazetteer of Jamnagar counted 1,200 bandhani workers in the district."
    history = "In 1971 the Jamnagar district Gazetteer recorded 1,200 people working in bandhani."
    ledger = ClaimLedger()
    first = cited("s1.b1.1", economics, "gazetteer-economics", FRATER_BOOK, economics)
    again = cited("s2.b1.1", history, "gazetteer-history", KHAMIR_ART, history)
    assert told(ledger, "s1", first) == [economics]
    assert told(ledger, "s2", again) == []


def test_a_miniature_of_1625_retold_in_other_words_is_said_once() -> None:
    first_said = "A Mughal miniature of 1625 shows a bidri huqqa base."
    retold = "Bidri huqqa bases appear in a Mughal miniature of 1625."
    ledger = ClaimLedger()
    assert told(ledger, "s1", cited("s1.b1.1", first_said, "miniature-a", EDWARDS, first_said)) == [
        first_said
    ]
    assert told(ledger, "s2", cited("s2.b1.1", retold, "miniature-b", IJTK, retold)) == []


def test_the_same_passage_of_one_source_told_again_without_a_number_is_said_once() -> None:
    passage = "harde, kut and alizarin are used together for the red of the cloth"
    chemistry = "Harde, kut and alizarin give Ajrakh cloth its red."
    materials = "The red of Ajrakh cloth comes from alizarin used together with harde and kut."
    ledger = ClaimLedger()
    assert told(ledger, "s1", cited("s1.b1.1", chemistry, "red-chemistry", FRATER_BOOK, passage)) == [
        chemistry
    ]
    again = cited("s2.b1.1", materials, "red-materials", FRATER_BOOK, f"{passage} in Kutch")
    assert told(ledger, "s2", again) == []


def test_two_steps_that_take_the_same_time_are_both_said() -> None:
    dyed = "The cloth is dyed in the indigo vat for 10 to 15 minutes."
    washed = "The cloth is washed in the river for 10 to 15 minutes."
    ledger = ClaimLedger()
    assert told(ledger, "s1", cited("s1.b1.1", dyed, "dyed", FRATER_BOOK, dyed)) == [dyed]
    assert told(ledger, "s2", cited("s2.b1.1", washed, "washed", FRATER_BOOK, washed)) == [washed]


def test_a_retelling_that_adds_a_figure_is_still_said() -> None:
    counted = "The 1971 Gazetteer of Jamnagar counted bandhani workers in the district."
    with_count = "The 1971 Gazetteer of Jamnagar counted 1,200 bandhani workers in the district."
    ledger = ClaimLedger()
    assert told(ledger, "s1", cited("s1.b1.1", counted, "counted", FRATER_BOOK, counted)) == [counted]
    again = cited("s2.b1.1", with_count, "with-count", KHAMIR_ART, with_count)
    assert told(ledger, "s2", again) == [with_count]
