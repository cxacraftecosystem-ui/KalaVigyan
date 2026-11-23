import copy
import hashlib
from collections.abc import Callable
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from app.research.explainer import Block

from ..contracts.phase_c_golden import phase_c_blocks

BLOCK = TypeAdapter(Block)
Change = Callable[[dict[str, Any]], None]


def changed(block_id: str, change: Change) -> dict[str, Any]:
    block = copy.deepcopy(phase_c_blocks()[block_id])
    change(block)
    return block


def rehashed(block: dict[str, Any], html: str) -> None:
    block["html"] = html
    block["htmlSha256"] = hashlib.sha256(html.encode("utf-8")).hexdigest()


def value(block: dict[str, Any], **fields: Any) -> None:
    block["values"][0].update(fields)


def option(block: dict[str, Any], index: int, **fields: Any) -> None:
    block["options"][index].update(fields)


def level(block: dict[str, Any], index: int, **fields: Any) -> None:
    block["levels"][index].update(fields)


def hypothesis(block: dict[str, Any]) -> None:
    sentence = block["options"][0]["outcomes"][0]["sentence"]
    sentence["level"] = "HYPOTHESIS"
    for citation in sentence["citations"]:
        citation["level"] = "HYPOTHESIS"


def unavailable(block: dict[str, Any]) -> None:
    block["options"][0]["outcomes"][0]["sentence"]["level"] = "UNAVAILABLE"


def reversed_points(block: dict[str, Any]) -> None:
    block["points"] = block["points"][::-1]
    block["places"][:3] = block["places"][:3][::-1]
    for index, point in enumerate(block["points"]):
        point["place"] = index


SIMULATION_RULES: list[tuple[Change, str]] = [
    (lambda b: value(b, stated="12 feet every year"), "which no cited quote says"),
    (lambda b: value(b, value=12.0), "does not state"),
    (lambda b: value(b, label="Fall of 40 feet"), "labelled with a figure"),
    (lambda b: value(b, datasetCode="CHIRPS_MONTHLY"), "not both"),
    (lambda b: value(b, citations=[]), "a figure a cited quote states"),
    (lambda b: b["values"].append(dict(b["values"][0])), "each value once"),
    (lambda b: b.update(htmlSha256="0" * 64), "SHA-256 of its own HTML"),
    (lambda b: b.update(title="Falls 40 feet a year"), "figure no value states"),
    (lambda b: b.update(concept="जल"), "no Latin letter"),
    (lambda b: rehashed(b, b["html"] + "<script>fetch(address);</script>"), "sandbox check: API fetch"),
    (lambda b: rehashed(b, b["html"] + "<p>Down 37 feet</p>"), "sandbox check: NUMBER"),
]
WHAT_IF_RULES: list[tuple[Change, str]] = [
    (lambda b: option(b, 2, label=b["options"][0]["label"].upper()), "each option once"),
    (lambda b: option(b, 0, materialId=None), "neither stored nor named"),
    (lambda b: option(b, 2, label="Al root boiled 40 minutes"), "figure its outcomes do not state"),
    (lambda b: b.update(changed="Red dye at 60 degrees"), "input named with a figure"),
    (lambda b: b["options"][1]["outcomes"].append(b["options"][1]["outcomes"][0]), "each outcome once"),
    (lambda b: b.update(options=b["options"][2:]), "at least 2"),
    (lambda b: b.update(options=[b["options"][2], b["options"][2] | {"label": "Lac"}]), "cites nothing"),
    (unavailable, "stored findings only"),
]
ZOOM_RULES: list[tuple[Change, str]] = [
    (lambda b: level(b, 1, media=b["levels"][1]["media"] | {"display": "LINK_CARD"}), "licensed image"),
    (lambda b: level(b, 0, district=None), "exactly its district"),
    (lambda b: level(b, 1, district=b["levels"][0]["district"]), "exactly its media and relevance"),
    (lambda b: level(b, 2, compound=None), "exactly its compound"),
    (lambda b: b.update(levels=b["levels"][::-1]), "level by level"),
    (lambda b: b.update(boundaryCaption=None), "boundary caption"),
    (lambda b: b.update(datasets=[]), "exactly when it maps a district"),
    (lambda b: level(b, 0, district=b["levels"][0]["district"] | {"name": "Surat"}), "does not name"),
    (lambda b: level(b, 2, compound=b["levels"][2]["compound"] | {"name": "Indigo"}), "does not name"),
]
TIMELINE_RULES: list[tuple[Change, str]] = [
    (
        lambda b: b["places"][1].update(latitude=23.4, longitude=69.6),
        "both coordinates of its item or district",
    ),
    (lambda b: b["places"][0].update(longitude=None), "both coordinates of its item or district"),
    (lambda b: b["points"][1].update(yearFrom=1587, yearTo=1587), "not stated"),
    (lambda b: (b["places"][3].update(name="Kutch"), b["places"][4].update(name="Sindh")), "states the move"),
    (lambda b: b["routes"][0].update(end=3), "two different places"),
    (lambda b: b["points"][0].update(place=9), "only listed places"),
    (
        lambda b: b["places"].append(
            {"name": "Barmer", "wikidataId": None, "latitude": None, "longitude": None}
        ),
        "each used",
    ),
    (lambda b: b["places"][4].update(name="Sindh"), "each place once"),
    (reversed_points, "time order"),
    (lambda b: b["points"][0].update(place=2), "order of first use"),
    (lambda b: b["places"][0].update(name="Cairo"), "sentence names"),
    (lambda b: b.update(boundaryCaption="Boundaries are indicative."), "boundary caption"),
]


def cases(block_id: str, rules: list[tuple[Change, str]]) -> list[Any]:
    return [
        pytest.param(block_id, change, message, id=f"{block_id}-{n}")
        for n, (change, message) in enumerate(rules)
    ]


@pytest.mark.parametrize(
    ("block_id", "change", "message"),
    [
        *cases("s1.b1", SIMULATION_RULES),
        *cases("s2.b1", WHAT_IF_RULES),
        *cases("s3.b1", ZOOM_RULES),
        *cases("s4.b1", TIMELINE_RULES),
    ],
)
def test_a_phase_c_block_that_breaks_a_rule_does_not_construct(
    block_id: str, change: Change, message: str
) -> None:
    with pytest.raises(ValidationError, match=message):
        BLOCK.validate_python(changed(block_id, change))


def test_a_what_if_outcome_that_is_a_hypothesis_keeps_its_level_to_be_labelled() -> None:
    block = BLOCK.validate_python(changed("s2.b1", hypothesis))
    outcome = block.options[0].outcomes[0]
    assert outcome.sentence.level == "HYPOTHESIS"
    assert [s.level for s in block.cited_sentences()] == [
        "HYPOTHESIS",
        "PROVISIONAL",
        "PROVISIONAL",
        "PROVISIONAL",
    ]


def test_a_zoom_story_maps_and_captions_only_a_district_its_sentence_names() -> None:
    unmapped = changed("s3.b1", lambda b: b.update(levels=b["levels"][1:], datasets=[], boundaryCaption=None))
    assert [level.level for level in BLOCK.validate_python(unmapped).levels] == ["WORKSHOP", "MOLECULE"]
    barmer = changed("s3.b1", lambda b: level(b, 0, district=b["levels"][0]["district"] | {"name": "Barmer"}))
    assert BLOCK.validate_python(barmer).levels[0].district.name == "Barmer"


def test_a_dataset_value_rests_on_a_listed_row_and_every_row_is_used() -> None:
    def on_rows(block: dict[str, Any], datasets: list[dict[str, Any]]) -> None:
        value(block, datasetCode="DR_DISTRICT_SHAPES", citations=[], stated=None)
        block["datasets"] = datasets

    boundary = phase_c_blocks()["s3.b1"]["datasets"]
    assert BLOCK.validate_python(changed("s1.b1", lambda b: on_rows(b, boundary))).cites_datasets()
    with pytest.raises(ValidationError, match="DR_DISTRICT_SHAPES missing"):
        BLOCK.validate_python(changed("s1.b1", lambda b: on_rows(b, [])))
    with pytest.raises(ValidationError, match="only the dataset rows its values use"):
        BLOCK.validate_python(changed("s1.b1", lambda b: b.update(datasets=boundary)))
