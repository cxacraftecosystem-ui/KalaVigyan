from __future__ import annotations

from collections.abc import Mapping, Sequence
from types import MappingProxyType

__all__ = ["FIXES_HEAD", "RULE_FIXES", "rule_fixes"]

FIELD_PROSE = (
    "edit_draft add facts in that field, each with its source and quote (search_sources, read_source); each "
    "draws as a sentence of the field's section, so three make it dense"
)
RULE_FIXES: Mapping[int, str] = MappingProxyType(
    {
        1: "edit_draft: remove the part whose title is a raw question and add it back with a stated title",
        2: (
            "give_pictures with the picture's page_url (an open-licence file page, such as one search_sources "
            "found) and slot MASTHEAD, then edit_draft add pictures [{contribution_id}]"
        ),
        3: "edit_draft remove the second masthead picture or the part that repeats it",
        4: (
            "edit_draft: remove the fact or component whose number its quotes do not state and add it back "
            "with the number its source states"
        ),
        6: (
            "edit_draft's lists.signature names the signature fact and one sentence cites it: if none does, "
            "edit_draft add it as a fact in its field"
        ),
        7: "edit_draft remove the repeated picture",
        9: (
            "edit_draft add components with each unit naming the claim_ids it rests on; a borrowed figure whose "
            "facts the page does not hold is not drawn, so place your own figure on this page's facts"
        ),
        10: "edit_draft: remove the unit that shows a progress state and add it back at rest",
        14: "give_pictures again with the picture's credit, then edit_draft add pictures [{contribution_id}]",
        15: "edit_draft add components whose cards each hold a unit that cites a fact, or remove the empty card",
        17: "edit_draft add the chart declared (form bars or line, its values from zero) in place of the drawn one",
        20: (
            "edit_draft add facts that name the mechanism in two or more sentences of its field, and a figure "
            "that draws it (your own component, or compose_component as a shortcut)"
        ),
        23: FIELD_PROSE,
        24: FIELD_PROSE,
        25: (
            "edit_draft: remove the figure each line names, whose unit repeats the sentence it quotes, and add "
            "it back with units that add to the prose"
        ),
        26: (
            f"{FIELD_PROSE}; a text that reads as a gap is named with its unit and its facts: edit_draft for "
            "the page's own unit, propose_facts for a fact stated from what its source finds, and an Admin "
            "retracts the gap's fact with stage_reviews"
        ),
        27: (
            "edit_draft: remove the figure and add it back drawn with the design's tokens and the kit "
            "(kit-stylesheet/1)"
        ),
        28: (
            "edit_draft: remove the component the drawing names and add it back fixed as its problem says; "
            "a toggle its lab draws is checked inside the lab"
        ),
    }
)
FIXES_HEAD = " Every failed rule has its tool; keep fixing and previewing while one fails: "


def rule_fixes(failed: Sequence[int]) -> str:
    named = [f"rule {number}, {RULE_FIXES[number]}" for number in sorted(set(failed)) if number in RULE_FIXES]
    return FIXES_HEAD + "; ".join(named) + "." if named else ""
