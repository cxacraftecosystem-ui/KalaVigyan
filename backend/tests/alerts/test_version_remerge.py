import uuid
from typing import Any

from app.services.version_merge import merged_version, remerged_version

from ..contracts.phase_b_golden import phase_b_blocks
from .test_version_merge import water_and_history
from .versions import base_version, follow_up_document

LOSER = "9d8c7b6a-5f4e-4d3c-8b2a-1f0e9d8c7b6a"


def second_version() -> Any:
    return merged_version(base_version(), follow_up_document(water_and_history()))


def geology(layer: str) -> dict[str, Any]:
    block = {**phase_b_blocks()["s2.b1"], "id": "s4.b1", "layer": layer}
    return {
        "id": "s4",
        "discipline": "GEOLOGY",
        "title": "The soil",
        "state": "READY",
        "blocks": [block],
        "searched": None,
    }


def test_a_follow_up_that_lost_the_race_is_renumbered_after_the_newer_version_s_blocks() -> None:
    loser = follow_up_document(water_and_history(), answer_id=LOSER)
    third = remerged_version(second_version(), loser)
    assert third is not None
    mark = third.mark
    assert (mark.version, mark.based_on, mark.answer_id) == (3, 2, uuid.UUID(LOSER))
    assert [(c.section_id, c.change, c.block_ids) for c in mark.changes] == [
        ("s2", "DEEPENED", ["s2.b3"]),
        ("s4", "DEEPENED", ["s4.b2"]),
    ]
    sections = {section.id: [block.id for block in section.blocks] for section in third.explainer.sections}
    assert sections == {
        "s1": ["s1.b1", "s1.b2"],
        "s2": ["s2.b1", "s2.b2", "s2.b3"],
        "s3": ["s3.b1"],
        "s4": ["s4.b1", "s4.b2"],
    }
    moved = third.explainer.sections[1].blocks[2]
    assert [sentence.id for sentence in moved.cited_sentences()][:1] == ["s2.b3.1"]


def test_a_new_field_the_newer_version_lacks_is_added_after_its_sections() -> None:
    history = water_and_history()[1]
    economics = {**history, "discipline": "ECONOMICS", "title": "Who makes a living"}
    third = remerged_version(second_version(), follow_up_document([economics], answer_id=LOSER))
    assert third is not None
    assert [(s.id, s.discipline, s.order) for s in third.explainer.sections][-1] == ("s5", "ECONOMICS", 5)
    assert [(c.section_id, c.change, c.block_ids) for c in third.mark.changes] == [("s5", "ADDED", ["s5.b1"])]


def test_a_second_layer_fits_a_newer_version_and_the_same_layer_does_not() -> None:
    newer = merged_version(base_version(), follow_up_document([geology("soil-ph-0-5cm")]))
    again = remerged_version(newer, follow_up_document([geology("soil-ph-0-5cm")], answer_id=LOSER))
    assert again is None
    other = remerged_version(newer, follow_up_document([geology("rainfall-annual")], answer_id=LOSER))
    assert other is not None
    (soil, rain) = other.explainer.sections[3].blocks
    assert [(soil.id, soil.layer), (rain.id, rain.layer)] == [
        ("s4.b1", "soil-ph-0-5cm"),
        ("s4.b2", "rainfall-annual"),
    ]
