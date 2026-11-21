import copy
from collections.abc import Callable
from typing import Any

import pytest
from pydantic import ValidationError

from app.models.component_kinds import COMPONENT_KINDS, PIECE_KINDS
from app.research.component_specs_science import SPEC_MODELS_SCIENCE
from app.research.component_specs_science_parts import ColourMix, SvgNode, TextBlock

from . import science_spec_fixtures as fixtures

SCIENCE_KINDS = {
    "reaction_player",
    "diagram",
    "choice_toggle",
    "molecule_3d",
    "structure_diagram",
    "dip_player",
    "stage_player",
    "equation_card",
    "model_explainer",
    "material_cards",
    "experiment_lab",
    "process_replay",
}
VALID: dict[str, Callable[[], dict[str, Any]]] = {
    "reaction_player": fixtures.reaction_player,
    "diagram": fixtures.chain_diagram,
    "choice_toggle": fixtures.choice_toggle,
    "molecule_3d": fixtures.molecule_3d,
    "structure_diagram": fixtures.structure_diagram,
    "dip_player": fixtures.dip_player,
    "stage_player": fixtures.stage_player,
    "equation_card": fixtures.equation_card,
    "model_explainer": fixtures.model_explainer,
    "material_cards": fixtures.material_cards,
    "experiment_lab": fixtures.experiment_lab,
    "process_replay": fixtures.process_replay,
}


def refused(kind: str, change: Callable[[dict[str, Any]], None]) -> None:
    spec = copy.deepcopy(VALID[kind]())
    change(spec)
    with pytest.raises(ValidationError):
        SPEC_MODELS_SCIENCE[kind].model_validate(spec)


def test_the_science_group_names_its_twelve_kinds_each_a_registered_piece_kind() -> None:
    assert set(SPEC_MODELS_SCIENCE) == SCIENCE_KINDS
    assert set(PIECE_KINDS) >= SCIENCE_KINDS
    assert SCIENCE_KINDS - {"reaction_player", "molecule_3d"} <= set(COMPONENT_KINDS)


@pytest.mark.parametrize("kind", sorted(SCIENCE_KINDS))
def test_a_valid_spec_of_each_kind_is_kept_as_written(kind: str) -> None:
    spec = VALID[kind]()
    assert SPEC_MODELS_SCIENCE[kind].model_validate(spec).model_dump(mode="json", by_alias=True) == spec


REFUSALS: list[tuple[str, Callable[[dict[str, Any]], None]]] = [
    ("equation_card", lambda spec: spec.update(why="why-1")),
    ("diagram", lambda spec: spec.update(drawing=fixtures.DOT)),
    ("diagram", lambda spec: spec["chain"]["links"].pop()),
    ("structure_diagram", lambda spec: spec["molecules"][0].update(cid=0)),
    ("molecule_3d", lambda spec: spec["key"][0].update(swatch="square")),
    ("material_cards", lambda spec: spec["cards"][0].update(swatch="--brand-purple")),
    ("model_explainer", lambda spec: spec["model"].update(sandbox="allow-scripts allow-same-origin")),
    ("model_explainer", lambda spec: spec["controls"].update(sliderAt=1001)),
    ("model_explainer", lambda spec: spec["model"].update(stylesheet="</style><script>")),
    ("process_replay", lambda spec: spec["stages"][0].update(startMs=600, endMs=600)),
    ("process_replay", lambda spec: spec["sources"][0].update(grade="E")),
    ("reaction_player", lambda spec: spec.update(current=3)),
    (
        "reaction_player",
        lambda spec: spec["steps"][0].update(
            scene={"whereIcon": fixtures.DOT, "where": "u0001", "art": [fixtures.DOT]}
        ),
    ),
    ("reaction_player", lambda spec: spec["steps"][0]["chemistry"]["parts"].pop()),
    ("dip_player", lambda spec: spec["phases"][0].update(pose="In the vat")),
    ("dip_player", lambda spec: spec["phases"][1].update(pose=spec["phases"][0]["pose"])),
    ("stage_player", lambda spec: spec["stages"][0].update(texts=[])),
    ("choice_toggle", lambda spec: spec["options"][1].update(value="madder")),
    (
        "choice_toggle",
        lambda spec: spec["textParts"][0]["chips"][0].update(source="KalaVigyan compound library"),
    ),
    ("experiment_lab", lambda spec: spec["experiments"].pop()),
]


@pytest.mark.parametrize(("kind", "change"), REFUSALS)
def test_a_spec_that_breaks_its_kinds_rule_is_refused(
    kind: str, change: Callable[[dict[str, Any]], None]
) -> None:
    refused(kind, change)


def test_every_kind_has_a_refusal_case() -> None:
    assert {kind for kind, _ in REFUSALS} == SCIENCE_KINDS


def test_a_drawing_paints_with_tokens_mask_white_or_a_mix_of_two_tokens() -> None:
    painted = [
        {"fill": "var(--dye-indigo)"},
        {"stroke": "rgba(255,255,255,.2)"},
        {"fill": "#fff"},
        {"fill": "color-mix(in srgb, var(--dye-cloth) 80%, var(--dye-mud))"},
        {"fill": "url(#tile-3)"},
    ]
    for attrs in painted:
        assert SvgNode.model_validate({"tag": "rect", "attrs": attrs}).attrs == attrs


@pytest.mark.parametrize(
    "attrs",
    [
        {"onclick": "alert(1)"},
        {"fill": "#5f01d1"},
        {"fill": "var(--brand-purple)"},
        {"fill": "url(https://example.org/a.svg#x)"},
        {"style": "background:url(https://example.org/x.png)"},
        {"href": "javascript:alert(1)"},
        {"fill": "color-mix(in srgb, var(--dye-cloth) 80%, red)"},
    ],
)
def test_a_drawing_refuses_handlers_foreign_references_and_untokened_paint(attrs: dict[str, str]) -> None:
    with pytest.raises(ValidationError):
        SvgNode.model_validate({"tag": "rect", "attrs": attrs})


def test_a_drawing_holds_drawing_elements_only() -> None:
    with pytest.raises(ValidationError):
        SvgNode.model_validate({"tag": "svg", "children": [{"tag": "script", "children": ["alert(1)"]}]})
    with pytest.raises(ValidationError):
        SvgNode.model_validate({"tag": "foreignObject"})


def test_spec_text_keeps_its_spaces_where_contract_models_strip_them() -> None:
    lane = fixtures.reaction_player()
    lane["steps"][0]["chemistry"]["parts"][0]["items"][0]["state"] = ["in the paste · "]
    spec = SPEC_MODELS_SCIENCE["reaction_player"].model_validate(lane)
    assert spec.model_dump(by_alias=True)["steps"][0]["chemistry"]["parts"][0]["items"][0]["state"] == [
        "in the paste · "
    ]


def test_a_colour_mix_shares_between_one_and_ninety_nine_per_cent() -> None:
    assert (
        ColourMix.model_validate({"first": "--dye-harda-dry", "share": 60, "second": "--dye-cloth"}).share
        == 60
    )
    for share in (0, 100):
        with pytest.raises(ValidationError):
            ColourMix.model_validate({"first": "--dye-harda-dry", "share": share, "second": "--dye-cloth"})


def test_a_text_block_names_a_unit_and_a_style() -> None:
    assert TextBlock.model_validate({"tag": "p", "style": "lab-lime", "unit": "u0889"}).style == "lab-lime"
    with pytest.raises(ValidationError):
        TextBlock.model_validate({"tag": "div", "style": None, "unit": "u0889"})
    with pytest.raises(ValidationError):
        TextBlock.model_validate({"tag": "p", "style": "Lab Lime", "unit": "u0889"})
