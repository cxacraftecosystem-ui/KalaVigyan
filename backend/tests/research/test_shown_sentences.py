from typing import Any

from app.research.blocks_insight import MeasureBlock
from app.research.blocks_place import SupplyMapBlock
from app.research.coverage_answers import field_sentences, shown_field_sentences
from app.research.coverage_eval import answer_measures, judge_message
from app.research.explainer import Explainer

from ..contracts.explainer_golden import DOCUMENT, golden_json
from ..contracts.phase_b_golden import phase_b_blocks
from ..contracts.phase_d_golden import phase_d_blocks

INDIGO = "Indigo came from Shikarpur in Sindh and was also grown in Dhamadka."
BLOCKS = "Blocks are carved from teak (sag); printers today buy blocks from block-makers in Pethapur near Gandhinagar."
AJRAKHPUR = (
    "At Ajrakhpur water once rose at a depth of 200 feet, "
    "but an artisan's later private borewell had to reach 450 feet."
)
ASKED = ["PROCESS", "GEOGRAPHY", "CHEMISTRY"]


def supply_map() -> SupplyMapBlock:
    return SupplyMapBlock.model_validate(phase_b_blocks()["s6.b1"])


def borewell_measure() -> MeasureBlock:
    block = phase_d_blocks()["s4.b1"]
    row = block["rows"][0]
    sentence = {**row["sentence"], "text": AJRAKHPUR}
    rows = [
        _feet(row, "200 feet", 200.0, 61.0, {**sentence, "id": "s4.b1.1"}),
        _feet(row, "450 feet", 450.0, 137.0, {**sentence, "id": "s4.b1.2"}),
    ]
    return MeasureBlock.model_validate({**block, "rows": rows})


def _feet(
    row: dict[str, Any], stated: str, feet: float, metres: float, sentence: dict[str, Any]
) -> dict[str, Any]:
    metric = {"low": metres, "high": None, "unit": "m"}
    return {**row, "stated": stated, "low": feet, "high": None, "metric": metric, "sentence": sentence}


def with_blocks(*blocks: Any) -> Explainer:
    explainer = Explainer.model_validate(golden_json(DOCUMENT))
    geography = explainer.sections[1]
    placed = geography.model_copy(update={"blocks": [*geography.blocks, *blocks]})
    return explainer.model_copy(update={"sections": [explainer.sections[0], placed, *explainer.sections[2:]]})


def test_a_block_shows_a_sentence_its_items_share_once_in_their_order() -> None:
    supply = supply_map()
    assert [s.text for s in supply.cited_sentences()] == [INDIGO, INDIGO, BLOCKS]
    assert [s.id for s in supply.shown_sentences()] == ["s6.b1.1", "s6.b1.3"]
    measure = borewell_measure()
    assert [s.id for s in measure.shown_sentences()] == ["s4.b1.1"]


def test_translated_copies_of_one_sentence_are_one_sentence_by_their_original() -> None:
    block = phase_b_blocks()["s6.b1"]
    links = [
        {
            **link,
            "sentence": {
                **link["sentence"],
                "text": f"Translated {n}",
                "translated": True,
                "original": INDIGO,
            },
        }
        for n, link in enumerate(block["links"][:2], start=1)
    ]
    supply = SupplyMapBlock.model_validate({**block, "links": [*links, block["links"][2]]})
    assert [s.text for s in supply.shown_sentences()] == ["Translated 1", BLOCKS]


def test_the_judge_reads_each_block_sentence_once_as_the_views_show_it() -> None:
    explainer = with_blocks(supply_map(), borewell_measure())
    message = judge_message("Where did the indigo come from?", explainer, ASKED)
    assert message.count(INDIGO) == 1
    assert message.count(AJRAKHPUR) == 1
    assert message.count(" citations)") == 12 + 3
    assert len(shown_field_sentences(explainer)) == 12 + 3


def test_the_rubric_still_counts_the_sentences_the_blocks_carry() -> None:
    explainer = with_blocks(supply_map(), borewell_measure())
    assert len(field_sentences(explainer)) == 12 + 5
    assert answer_measures(explainer, ASKED).sentences == 12 + 5
