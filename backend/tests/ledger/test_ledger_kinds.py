from typing import Any

import pytest
from pydantic import TypeAdapter

from app.research.blocks import BlockBase
from app.research.explainer import Block, with_payload_sentences
from app.services.claim_ledger import ClaimLedger

from ..contracts.blocks_golden import QUANTITIES
from ..contracts.explainer_golden import golden_json
from ..contracts.phase_b_golden import phase_b, phase_b_blocks
from ..contracts.phase_c_golden import phase_c, phase_c_blocks
from ..contracts.phase_d_golden import phase_d, phase_d_blocks
from .indigo_blocks import ITOKRI, ZAVERI, card, ladder, pictures, prose, zoom
from .indigo_claims import GREEN_BLUE, IMMERSED, SOURCES, TWO_SHADES
from .shown import repeated_sentences

BLOCK = TypeAdapter(Block)
REFS = {
    ref["id"]: ref for ref in (*SOURCES, *phase_b()["sources"], *phase_c()["sources"], *phase_d()["sources"])
}


def admitted(ledger: ClaimLedger, section_id: str, *payloads: dict[str, Any]) -> list[BlockBase]:
    return ledger.admit(section_id, [BLOCK.validate_python(payload) for payload in payloads], REFS)


def said(block_id: str, sentence: Any) -> dict[str, Any]:
    payload = prose(block_id, (sentence.text, ()))
    payload["sentences"][0]["citations"] = [
        c.model_dump(mode="json", by_alias=True) for c in sentence.citations
    ]
    return payload


def test_a_ladder_leaves_out_a_stage_whose_every_sentence_a_card_already_showed() -> None:
    ledger = ClaimLedger()
    shown = admitted(ledger, "s1", card("s1.b2", "Indigo", "indigo", TWO_SHADES, GREEN_BLUE))
    shown += admitted(ledger, "s2", ladder("s2.b1"))
    (steps,) = [block for block in shown if block.kind == "process_ladder"]
    assert [(stage.ordinal, [s.text for s in stage.sentences]) for stage in steps.stages] == [
        (9, [IMMERSED.text])
    ]
    assert repeated_sentences(shown) == 0


def test_a_stage_that_keeps_some_sentences_takes_the_level_of_what_it_keeps() -> None:
    steps = ladder("s2.b1")
    eighth = steps["stages"][0]
    eighth["sentences"][1]["level"] = "REVIEWED"
    ledger = ClaimLedger()
    admitted(ledger, "s1", card("s1.b2", "Indigo", "indigo", TWO_SHADES))
    (kept,) = admitted(ledger, "s2", steps)
    stage = kept.stages[0]
    assert ([s.text for s in stage.sentences], stage.level) == ([GREEN_BLUE.text], "REVIEWED")


def test_two_seats_keep_differing_when_one_reading_was_already_said_in_prose() -> None:
    historian, anthropologist = phase_b_blocks()["s5.b1"], phase_b_blocks()["s5.b2"]
    view = BLOCK.validate_python(historian).differs[0].this_view
    ledger = ClaimLedger()
    shown = admitted(ledger, "s1", said("s1.b1", view))
    shown += admitted(ledger, "s5", historian, anthropologist)
    assert [(block.kind, [d.seat for d in getattr(block, "differs", [])]) for block in shown] == [
        ("prose", []),
        ("expert_view", ["ANTHROPOLOGIST"]),
        ("expert_view", ["HISTORIAN"]),
    ]
    assert repeated_sentences(shown) == 1


def test_two_seats_do_not_differ_again_over_two_readings_the_page_already_said() -> None:
    historian, anthropologist = phase_b_blocks()["s5.b1"], phase_b_blocks()["s5.b2"]
    difference = BLOCK.validate_python(historian).differs[0]
    ledger = ClaimLedger()
    shown = admitted(ledger, "s1", said("s1.b1", difference.this_view), said("s1.b2", difference.other_view))
    shown += admitted(ledger, "s5", historian, anthropologist)
    assert [(block.kind, [d.seat for d in getattr(block, "differs", [])]) for block in shown] == [
        ("prose", []),
        ("prose", []),
        ("expert_view", []),
        ("expert_view", []),
    ]
    assert repeated_sentences(shown) == 0


def test_a_zoom_never_shows_a_picture_an_earlier_section_showed() -> None:
    story = zoom("s3.b1")
    story["levels"][0]["media"] = ZAVERI
    ledger = ClaimLedger()
    admitted(ledger, "s1", prose("s1.b1", ("The cloth turns blue in air.", (GREEN_BLUE,))))
    (picture,) = admitted(ledger, "s1", pictures("s1.b2", (ZAVERI, (GREEN_BLUE,))))
    (kept,) = admitted(ledger, "s3", story)
    assert str(picture.items[0].media.id) == ZAVERI["id"]
    assert [level.level for level in kept.levels] == ["CLOTH", "MOLECULE"]
    assert ZAVERI["id"] not in {str(level.media.id) for level in kept.levels if level.media}


def test_a_zoom_never_shows_a_shop_s_picture() -> None:
    story = zoom("s3.b1")
    shop = {
        **ITOKRI,
        "display": "INLINE",
        "title": "Kutch Ajrakh cloth",
        "licence": "CC BY 2.0",
        "author": "a",
    }
    story["levels"][1]["media"] = shop
    (kept,) = admitted(ClaimLedger(), "s3", story)
    assert [level.level for level in kept.levels] == ["WORKSHOP", "MOLECULE"]


def test_a_picture_a_zoom_showed_is_not_shown_again() -> None:
    ledger = ClaimLedger()
    admitted(ledger, "s3", prose("s3.b1", ("The cloth turns blue in air.", (GREEN_BLUE,))), zoom("s3.b2"))
    workshop = BLOCK.validate_python(zoom("s3.b2")).levels[0].media
    again = {**ZAVERI, "id": str(workshop.id), "pageUrl": workshop.page_url, "imageUrl": workshop.image_url}
    assert admitted(ledger, "s3", pictures("s3.b3", (again, (GREEN_BLUE,)))) == []


def test_any_other_story_block_leaves_out_an_item_already_said_word_for_word() -> None:
    seasons = phase_b_blocks()["s3.b1"]
    (row,) = BLOCK.validate_python(seasons).rows
    ledger = ClaimLedger()
    shown = admitted(ledger, "s1", said("s1.b1", row.sentence))
    assert admitted(ledger, "s3", seasons) == []
    assert [block.kind for block in admitted(ClaimLedger(), "s3", seasons)] == ["seasons"]
    assert repeated_sentences(shown) == 0


def test_a_compare_row_left_with_one_craft_goes_and_the_others_stay_in_their_columns() -> None:
    compare = phase_d_blocks()["s3.b1"]
    first = BLOCK.validate_python(compare).rows[0].cells[0]
    ledger = ClaimLedger()
    admitted(ledger, "s1", said("s1.b1", first.sentence))
    (kept,) = admitted(ledger, "s3", compare)
    assert [row.facet for row in kept.rows] == ["MATERIALS", "GEOGRAPHY", "HISTORY", "ECONOMICS"]
    assert kept.rows[0].term.key == "indigo"
    assert [len(row.cells) for row in kept.rows] == [2, 2, 2, 2]


def test_a_card_leaves_out_a_fact_whose_claims_the_prose_showed_in_other_words() -> None:
    ledger = ClaimLedger()
    admitted(
        ledger,
        "s1",
        prose("s1.b1", ("Lifted from the vat, the cloth goes from green to blue.", (GREEN_BLUE,))),
    )
    (kept,) = admitted(ledger, "s2", card("s2.b1", "Indigo", "indigo", GREEN_BLUE, TWO_SHADES))
    assert [fact.text for fact in kept.facts] == [TWO_SHADES.text]


def test_a_card_whose_every_fact_was_shown_goes_even_when_it_shows_a_formula() -> None:
    ledger = ClaimLedger()
    admitted(ledger, "s1", prose("s1.b1", (GREEN_BLUE.text, (GREEN_BLUE,)), (TWO_SHADES.text, (TWO_SHADES,))))
    assert admitted(ledger, "s2", card("s2.b1", "Indigo", "indigo", GREEN_BLUE, TWO_SHADES)) == []


def test_a_generated_explainer_of_one_concept_is_shown_once_per_answer() -> None:
    (explained,) = [payload for payload in phase_c_blocks().values() if payload["kind"] == "simulation"]
    ledger = ClaimLedger()
    first = admitted(ledger, "s1", {**explained, "id": "s1.b9", "reuse": None})
    again = admitted(
        ledger, "s4", {**explained, "id": "s4.b9", "reuse": None, "concept": explained["concept"].upper()}
    )
    other = admitted(
        ledger, "s5", {**explained, "id": "s5.b9", "reuse": None, "concept": "Another mechanism"}
    )
    assert ([b.id for b in first], again, [b.id for b in other]) == (["s1.b9"], [], ["s5.b9"])


def retold(payload: dict[str, Any], block_id: str) -> dict[str, Any]:
    def told(sentence: dict[str, Any]) -> dict[str, Any]:
        return {**sentence, "id": f"{sentence['id']}x", "text": f"{sentence['text']} Told again."}

    return with_payload_sentences({**payload, "id": block_id, "reuse": None}, told)


@pytest.mark.parametrize(
    ("kind", "blocks"),
    [("seasons", phase_b_blocks), ("supply_map", phase_b_blocks), ("zoom_story", phase_c_blocks)],
)
def test_a_craft_level_story_is_shown_once_per_answer_even_when_told_in_other_words(
    kind: str, blocks: Any
) -> None:
    (story,) = [payload for payload in blocks().values() if payload["kind"] == kind]
    ledger = ClaimLedger()
    first = admitted(ledger, "s1", {**story, "id": "s1.b9", "reuse": None})
    again = admitted(ledger, "s4", retold(story, "s4.b9"))
    assert ([block.id for block in first], again) == (["s1.b9"], [])
    assert [block.id for block in admitted(ClaimLedger(), "s4", retold(story, "s4.b9"))] == ["s4.b9"]


def quantities_sections() -> list[dict[str, Any]]:
    return golden_json(QUANTITIES)["sections"]


def test_a_table_whose_every_sentence_was_said_keeps_each_row_under_the_sentence_that_said_it() -> None:
    (table,) = quantities_sections()[0]["blocks"]
    sentences = list({row["sentence"]["text"]: row["sentence"] for row in table["rows"]}.values())
    said = [{**sentence, "id": f"s1.b9.{n}"} for n, sentence in enumerate(sentences, start=1)]
    ledger = ClaimLedger()
    shown = admitted(
        ledger, "s1", {"id": "s1.b9", "kind": "prose", "version": 1, "reuse": None, "sentences": said}
    )
    shown += admitted(ledger, "s1", table)
    kept = shown[-1]
    assert [row.shown_in for row in kept.rows] == ["s1.b9.1", "s1.b9.1", "s1.b9.2", "s1.b9.3", "s1.b9.4"]
    assert list(kept.shown_sentences()) == []
    assert repeated_sentences(shown) == 0


def test_a_stored_table_names_where_a_sentence_is_said_only_when_this_answer_says_it() -> None:
    _, table = quantities_sections()[1]["blocks"]
    (kept,) = admitted(ClaimLedger(), "s2", table)
    assert [row.shown_in for row in kept.rows] == [None, None, None, None, None]
    assert len(list(kept.shown_sentences())) == 4
