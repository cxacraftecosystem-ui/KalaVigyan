from typing import Any

from pydantic import TypeAdapter

from app.research.blocks import BlockBase
from app.research.explainer import Block
from app.services.claim_ledger import ClaimLedger

from .indigo_blocks import block, card, molecule
from .indigo_claims import GREEN_BLUE, IMMERSED, OXIDISES, REVERTS, SOURCES, TWO_SHADES, Claim, stated, uid

BLOCK = TypeAdapter(Block)
REFS = {ref["id"]: ref for ref in SOURCES}
VAT_STAGE = uid("stage/indigo-vat")
WASH_STAGE = uid("stage/washing")


def admitted(ledger: ClaimLedger, section_id: str, payload: dict[str, Any]) -> list[BlockBase]:
    return ledger.admit(section_id, [BLOCK.validate_python(payload)], REFS)


def what_if(block_id: str, stage: str, *options: tuple[str, Claim]) -> dict[str, Any]:
    return block(
        block_id,
        "what_if",
        changed="The dye",
        stageId=stage,
        options=[
            {
                "label": label,
                "materialId": uid(f"material/{label.casefold()}"),
                "termKey": None,
                "outcomes": [{"sentence": stated(f"{block_id}.{n}", claim), "reactionId": None}],
            }
            for n, (label, claim) in enumerate(options, 1)
        ],
    )


def test_a_card_of_a_material_an_earlier_section_carded_is_not_shown_again() -> None:
    ledger = ClaimLedger()
    assert len(admitted(ledger, "s2", card("s2.b2", "Indigo", "indigo", GREEN_BLUE))) == 1
    assert admitted(ledger, "s4", card("s4.b2", "Indigo", "indigo", TWO_SHADES)) == []


def test_a_card_of_another_material_is_still_shown_in_the_later_section() -> None:
    ledger = ClaimLedger()
    admitted(ledger, "s2", card("s2.b2", "Indigo", "indigo", GREEN_BLUE))
    (kept,) = admitted(ledger, "s4", card("s4.b2", "Lime", "lime", TWO_SHADES))
    assert kept.id == "s4.b2"


def test_a_molecule_an_earlier_section_drew_is_not_drawn_again() -> None:
    ledger = ClaimLedger()
    assert len(admitted(ledger, "s2", molecule("s2.b3"))) == 1
    assert admitted(ledger, "s4", molecule("s4.b3")) == []


def test_a_what_if_setting_the_same_two_choices_of_one_stage_side_by_side_is_shown_once() -> None:
    ledger = ClaimLedger()
    first = what_if("s2.b4", VAT_STAGE, ("Natural indigo", GREEN_BLUE), ("German indigo", OXIDISES))
    again = what_if(
        "s4.b4",
        VAT_STAGE,
        ("Natural indigo", TWO_SHADES),
        ("German indigo", IMMERSED),
        ("Woad", REVERTS),
    )
    assert len(admitted(ledger, "s2", first)) == 1
    assert admitted(ledger, "s4", again) == []


def test_a_what_if_of_another_input_of_the_same_stage_is_still_shown() -> None:
    ledger = ClaimLedger()
    admitted(
        ledger, "s2", what_if("s2.b4", VAT_STAGE, ("Natural indigo", GREEN_BLUE), ("German indigo", OXIDISES))
    )
    other = what_if("s4.b4", VAT_STAGE, ("Natural indigo", TWO_SHADES), ("Lime", IMMERSED))
    (kept,) = admitted(ledger, "s4", other)
    assert [option.label for option in kept.options] == ["Natural indigo", "Lime"]


def test_the_same_choices_at_another_stage_are_another_what_if() -> None:
    ledger = ClaimLedger()
    admitted(
        ledger, "s2", what_if("s2.b4", VAT_STAGE, ("Natural indigo", GREEN_BLUE), ("German indigo", OXIDISES))
    )
    elsewhere = what_if("s4.b4", WASH_STAGE, ("Natural indigo", TWO_SHADES), ("German indigo", IMMERSED))
    assert [block.id for block in admitted(ledger, "s4", elsewhere)] == ["s4.b4"]
