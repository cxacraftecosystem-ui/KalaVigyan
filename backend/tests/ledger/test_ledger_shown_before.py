from typing import Any

from pydantic import TypeAdapter

from app.research.blocks import BlockBase
from app.research.explainer import Block
from app.services.claim_ledger import ClaimLedger

from .indigo_blocks import ZAVERI, card, pictures, prose, supply
from .indigo_claims import GREEN_BLUE, SOURCES, TWO_SHADES

BLOCK = TypeAdapter(Block)
REFS = {ref["id"]: ref for ref in SOURCES}
GREEN_THEN_BLUE = "The cloth comes out of the vat green and turns blue in the air."
TWO_PRINTINGS = "For two shades of blue the cloth is printed again between dips in the vat."
BLUE_IN_AIR = "The cloth turns blue in air."


def admitted(ledger: ClaimLedger, section_id: str, payload: dict[str, Any]) -> list[BlockBase]:
    return ledger.admit(section_id, [BLOCK.validate_python(payload)], REFS)


def shown_before(*payloads: dict[str, Any]) -> ClaimLedger:
    ledger = ClaimLedger()
    ledger.note_shown(BLOCK.validate_python(payload) for payload in payloads)
    return ledger


def test_a_fact_the_explainer_already_says_is_left_out_of_a_new_section() -> None:
    ledger = shown_before(prose("s1.b1", (GREEN_THEN_BLUE, (GREEN_BLUE,))))
    again = prose("s4.b1", (GREEN_THEN_BLUE, (GREEN_BLUE,)), (TWO_PRINTINGS, (TWO_SHADES,)))
    (kept,) = admitted(ledger, "s4", again)
    assert [sentence.text for sentence in kept.cited_sentences()] == [TWO_PRINTINGS]


def test_a_once_per_answer_story_the_explainer_shows_is_not_shown_again() -> None:
    assert len(admitted(ClaimLedger(), "s4", supply("s4.b3"))) == 1
    assert admitted(shown_before(supply("s1.b3")), "s4", supply("s4.b3")) == []


def test_a_material_the_explainer_carded_is_not_carded_again() -> None:
    ledger = shown_before(card("s1.b2", "Indigo", "indigo", GREEN_BLUE))
    assert admitted(ledger, "s4", card("s4.b2", "Indigo", "indigo", TWO_SHADES)) == []


def test_a_picture_the_explainer_shows_is_not_shown_again() -> None:
    fresh = ClaimLedger()
    admitted(fresh, "s4", prose("s4.b1", (BLUE_IN_AIR, (GREEN_BLUE,))))
    assert len(admitted(fresh, "s4", pictures("s4.b2", (ZAVERI, (GREEN_BLUE,))))) == 1
    ledger = shown_before(pictures("s1.b2", (ZAVERI, (GREEN_BLUE,))))
    assert len(admitted(ledger, "s4", prose("s4.b1", (BLUE_IN_AIR, (GREEN_BLUE,))))) == 1
    assert admitted(ledger, "s4", pictures("s4.b2", (ZAVERI, (GREEN_BLUE,)))) == []
