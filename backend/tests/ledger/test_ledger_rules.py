from typing import Any

from pydantic import TypeAdapter

from app.research.explainer import Block, Explainer
from app.services.claim_ledger import COVERED_NOTE, ClaimLedger
from app.services.ledgered_explainer import ledgered_explainer

from ..contracts.phase_b_golden import phase_b, phase_b_blocks
from .indigo_answer import recorded_indigo
from .indigo_blocks import prose
from .indigo_claims import FERMENTED, VAT_SOLUBLE

BLOCK = TypeAdapter(Block)
GOLDEN_SOURCES = {ref["id"]: ref for ref in phase_b()["sources"]}


def golden(block_id: str, **changes: Any) -> Block:
    return BLOCK.validate_python({**phase_b_blocks()[block_id], **changes})


def test_an_answer_draws_one_region_story() -> None:
    ledger = ClaimLedger()
    first = ledger.admit("s1", [golden("s1.b1")], GOLDEN_SOURCES)
    again = ledger.admit("s3", [golden("s1.b1", id="s3.b2")], GOLDEN_SOURCES)
    assert ([block.id for block in first], again) == (["s1.b1"], [])


def take_said_first(historian: Block) -> ClaimLedger:
    (take,) = historian.take
    said = prose("s1.b1", (take.text, ()))
    said["sentences"][0]["citations"] = [c.model_dump(mode="json", by_alias=True) for c in take.citations]
    ledger = ClaimLedger()
    ledger.admit("s1", [BLOCK.validate_python(said)], GOLDEN_SOURCES)
    return ledger


def test_a_seat_whose_take_was_shown_stays_for_its_difference_and_keeps_it() -> None:
    historian, anthropologist = golden("s5.b1"), golden("s5.b2")
    shown = take_said_first(historian).admit("s5", [historian, anthropologist], GOLDEN_SOURCES)
    assert [(view.seat, [d.seat for d in view.differs]) for view in shown] == [
        ("HISTORIAN", ["ANTHROPOLOGIST"]),
        ("ANTHROPOLOGIST", ["HISTORIAN"]),
    ]


def test_a_seat_with_nothing_new_and_no_difference_leaves() -> None:
    historian, anthropologist = golden("s5.b1", differs=[]), golden("s5.b2", differs=[])
    shown = take_said_first(historian).admit("s5", [historian, anthropologist], GOLDEN_SOURCES)
    assert [(view.seat, view.differs, view.agrees_with) for view in shown] == [("ANTHROPOLOGIST", [], [])]


def test_a_pair_already_shown_as_a_difference_is_left_out_the_second_time() -> None:
    ledger = ClaimLedger()
    first = ledger.admit("s5", [golden("s5.b1"), golden("s5.b2")], GOLDEN_SOURCES)
    again = ledger.admit("s6", [golden("s5.b1", id="s6.b1"), golden("s5.b2", id="s6.b2")], GOLDEN_SOURCES)
    assert ([len(view.differs) for view in first], again) == ([1, 1], [])


def test_two_seats_both_bringing_something_new_keep_their_difference() -> None:
    shown = ClaimLedger().admit("s5", [golden("s5.b1"), golden("s5.b2")], GOLDEN_SOURCES)
    assert [(view.seat, [d.seat for d in view.differs]) for view in shown] == [
        ("HISTORIAN", ["ANTHROPOLOGIST"]),
        ("ANTHROPOLOGIST", ["HISTORIAN"]),
    ]


def test_a_translated_sentence_whose_english_was_shown_is_a_repeat() -> None:
    ledger = ClaimLedger()
    ledger.admit("s1", [BLOCK.validate_python(prose("s1.b1", (FERMENTED.text, (FERMENTED,))))], {})
    hindi = prose("s2.b1", ("प्राकृतिक नील को चूने, खजूर और सोडा के साथ सड़ाया जाता है।", (VAT_SOLUBLE,)))
    hindi["sentences"][0] |= {"translated": True, "original": FERMENTED.text}
    assert ledger.admit("s2", [BLOCK.validate_python(hindi)], {}) == []


def test_a_section_whose_every_block_was_already_shown_says_it_is_covered() -> None:
    recorded = recorded_indigo().model_dump(mode="json", by_alias=True)
    echo = {**recorded["sections"][0], "id": "s6", "order": 6, "title": "Again"}
    echo["blocks"] = [{**block, "id": block["id"].replace("s1.", "s6.", 1)} for block in echo["blocks"]]
    rebuilt = ledgered_explainer(
        Explainer.model_validate({**recorded, "sections": [*recorded["sections"], echo]})
    )
    last = rebuilt.sections[-1]
    assert (last.id, last.state, last.blocks, last.searched) == ("s6", "EMPTY", [], COVERED_NOTE)
