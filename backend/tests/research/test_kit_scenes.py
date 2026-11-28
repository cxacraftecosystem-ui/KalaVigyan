import copy
import json
import re
import uuid
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from app.research.component_specs import checked_spec
from app.research.component_specs_general_delivery import DeliveredUnit, spec_problems
from app.research.component_specs_kit_scene import KIT_SCENE_KINDS, KitScene, kit_scenes, scene_form
from app.research.component_specs_science_players import DRAWN_STAGE, REST_SCENE
from app.research.drawn_art import SCENE_POINTER, scene_problems

from . import science_spec_fixtures as science

SPECS = Path(__file__).resolve().parents[2] / "app" / "data" / "monographs" / "Kutch-Ajrakh" / "specs"
FACT = uuid.UUID("7c1f5a02-3b4e-4d8a-9f61-0e2d4b6a8c13")
REF = re.compile(r"^u\d{4}$")
CLOTH = {"part": "cloth", "form": "swatch", "material": "--dye-madder", "label": "u0601"}
BATH = {"part": "bath", "vessel": "pot", "piece": "--dye-bidri-black", "label": "u0602"}
HEAT = {"part": "heat", "source": "fire", "label": "u0603"}
WATER = {"part": "water", "form": "running", "label": "u0604"}
TAKES = {"parts": [CLOTH], "motion": "take"}
DIPS = {"parts": [BATH, HEAT], "motion": "dip"}
STILL = {"parts": [HEAT, WATER]}
SEAL = {"parts": [{"part": "piece", "shape": "vessel", "material": "--dye-bidri-black", "label": "u0605"}]}
LINE_WORK = {
    "tag": "svg",
    "attrs": {"viewBox": "0 0 120 80"},
    "children": [
        {
            "tag": "rect",
            "attrs": {
                "x": str(4 + 18 * at),
                "y": "20",
                "width": "14",
                "height": "14",
                "fill": "var(--sunk)",
                "stroke": "var(--ink-1)",
            },
        }
        for at in range(6)
    ],
}


def kit_reaction_player() -> dict[str, Any]:
    spec = science.reaction_player()
    spec["scenes"] = []
    spec["steps"][0]["scene"] = {"where": "u0611", "art": DIPS}
    spec["steps"][1]["scene"] = {"where": "u0612", "art": TAKES}
    return spec


def kit_dip_player() -> dict[str, Any]:
    spec = science.dip_player()
    spec["scene"] = TAKES
    spec["phases"][0]["drawing"] = DIPS
    spec["phases"][1]["drawing"] = TAKES
    spec["phases"][2]["drawing"] = STILL
    return spec


def kit_stage_player() -> dict[str, Any]:
    return {**science.stage_player(), "drawing": STILL}


def kit_choice_toggle() -> dict[str, Any]:
    spec = science.choice_toggle()
    spec["visualParts"] = [{"part": "stage", "drawing": STILL, "note": None, "noteHook": None}]
    return spec


def kit_label_card() -> dict[str, Any]:
    return {
        "variant": "gi",
        "kicker": "u0844",
        "seal": SEAL,
        "sentence": "u0846",
        "inset": None,
        "facts": [{"term": "u0852", "value": "u0853"}],
    }


KIT_SPECS = {
    "reaction_player": kit_reaction_player,
    "dip_player": kit_dip_player,
    "stage_player": kit_stage_player,
    "choice_toggle": kit_choice_toggle,
    "label_card": kit_label_card,
}


def refs(value: Any) -> set[str]:
    if isinstance(value, str):
        return {value} if REF.match(value) else set()
    if isinstance(value, dict):
        return {ref for item in value.values() for ref in refs(item)}
    if isinstance(value, list):
        return {ref for item in value for ref in refs(item)}
    return set()


def units(spec: dict[str, Any], uncited: frozenset[str] = frozenset()) -> dict[str, DeliveredUnit]:
    return {
        ref: DeliveredUnit(text="A label", claim_ids=[] if ref in uncited else [FACT])
        for ref in sorted(refs(spec))
    }


def test_the_five_kinds_that_take_a_kit_scene_are_the_players_the_toggle_and_the_label_card() -> None:
    assert set(KIT_SPECS) == KIT_SCENE_KINDS


@pytest.mark.parametrize("kind", sorted(KIT_SPECS))
def test_each_scene_slot_takes_a_kit_scene_kept_as_written(kind: str) -> None:
    spec = KIT_SPECS[kind]()
    assert checked_spec(kind, spec).model_dump(mode="json", by_alias=True) == spec
    assert spec_problems(kind, spec, units(spec)) == []


@pytest.mark.parametrize("kind", sorted(KIT_SPECS))
def test_each_scene_slot_still_takes_its_free_drawing(kind: str) -> None:
    spec = KIT_SPECS[kind]()
    drawn = json.loads(json.dumps(spec).replace(json.dumps(STILL), json.dumps(LINE_WORK)))
    drawn = json.loads(json.dumps(drawn).replace(json.dumps(SEAL), json.dumps(LINE_WORK)))
    if kind == "reaction_player":
        drawn["steps"] = [{**step, "scene": None} for step in drawn["steps"]]
        drawn["scenes"] = [LINE_WORK]
    if kind == "dip_player":
        drawn["scene"] = LINE_WORK
    assert [path for path, _ in kit_scenes(checked_spec(kind, drawn))] == (
        ["phases[0].drawing", "phases[1].drawing"] if kind == "dip_player" else []
    )
    assert spec_problems(kind, drawn, units(drawn)) == []


def test_a_kit_scene_is_told_from_a_drawing_by_its_parts() -> None:
    assert scene_form(DIPS) == "kit"
    assert scene_form(LINE_WORK) == "drawn"
    assert scene_form([LINE_WORK]) == "drawn"
    assert scene_form(KitScene.model_validate(STILL)) == "kit"


def test_a_kit_scene_holds_one_to_three_parts_and_its_motion_explains_one_of_them() -> None:
    with pytest.raises(ValidationError, match="at least 1"):
        KitScene.model_validate({"parts": []})
    with pytest.raises(ValidationError, match="at most 3"):
        KitScene.model_validate({"parts": [CLOTH, BATH, HEAT, WATER]})
    with pytest.raises(
        ValidationError,
        match="the dip motion explains a bath part with a piece in it, which this scene does not hold",
    ):
        KitScene.model_validate({"parts": [CLOTH], "motion": "dip"})
    with pytest.raises(ValidationError, match="depicted material"):
        KitScene.model_validate({"parts": [{**CLOTH, "material": "--indigo"}]})


@pytest.mark.parametrize("kind", ["stage_player", "choice_toggle", "label_card"])
def test_a_scene_that_rests_as_drawn_names_no_motion(kind: str) -> None:
    spec = json.loads(json.dumps(KIT_SPECS[kind]()).replace(json.dumps(STILL), json.dumps(TAKES)))
    spec = json.loads(json.dumps(spec).replace(json.dumps(SEAL), json.dumps(TAKES)))
    with pytest.raises(ValidationError, match="names no motion"):
        checked_spec(kind, spec)


def test_a_step_drawn_by_hand_shows_its_where_icon_and_a_kit_step_draws_where_it_happens() -> None:
    spec = kit_reaction_player()
    assert (
        "whereIcon" not in checked_spec("reaction_player", spec).model_dump(mode="json")["steps"][0]["scene"]
    )
    spec["steps"][0]["scene"] = {"where": "u0611", "art": [LINE_WORK]}
    with pytest.raises(ValidationError, match="where icon"):
        checked_spec("reaction_player", spec)
    spec["steps"][0]["scene"]["whereIcon"] = science.DOT
    assert checked_spec("reaction_player", spec)


def test_every_kit_scene_label_cites_a_fact_named_by_its_place() -> None:
    spec = kit_dip_player()
    assert spec_problems("dip_player", spec, units(spec, frozenset({"u0601", "u0604"}))) == [
        "the unit u0601, the label of the kit scene at scene's cloth part, cites no fact: a kit part's label "
        "rests on the facts that state it",
        "the unit u0601, the label of the kit scene at phases[1].drawing's cloth part, cites no fact: a kit "
        "part's label rests on the facts that state it",
        "the unit u0604, the label of the kit scene at phases[2].drawing's water part, cites no fact: a kit "
        "part's label rests on the facts that state it",
    ]


def test_a_free_scene_that_paints_what_a_kit_part_draws_is_refused_naming_the_part() -> None:
    spec = kit_dip_player()
    painted = copy.deepcopy(LINE_WORK)
    painted["children"].append(
        {
            "tag": "rect",
            "attrs": {"x": "10", "y": "40", "width": "60", "height": "30", "fill": "var(--dye-indigo)"},
        }
    )
    painted["children"].append({"tag": "title", "children": ["A cloth lifted from the vat"]})
    spec["phases"][0]["drawing"] = painted
    pointer = SCENE_POINTER.format(kind="dip_player")
    assert spec_problems("dip_player", spec, units(spec)) == [
        "the dip_player's drawing at phases[0].drawing paints --dye-indigo by hand, which the kit's cloth part "
        f"draws textured, framed and named in a key; {pointer}"
    ]
    spec["phases"][0]["drawing"] = LINE_WORK
    assert spec_problems("dip_player", spec, units(spec)) == []


def test_kutch_ajrakh_s_authored_dip_would_be_refused_from_a_contributor_and_is_never_rechecked() -> None:
    authored = json.loads((SPECS / "shared__chemistry__indigo-vat-dip.json").read_text(encoding="utf-8"))
    dumped = checked_spec("dip_player", authored).model_dump(mode="json")
    assert list(kit_scenes(checked_spec("dip_player", authored))) == []
    assert any(
        " by hand, which the kit's " in problem for problem in scene_problems("dip_player", dumped, {})
    )


CARVED = {"parts": [{"part": "block", "motif": "star", "paste": "--dye-kut", "label": "u0606"}]}
STAGE_UNITS = (810, 820, 850)


def staged_player(*scenes: Any) -> dict[str, Any]:
    spec = kit_stage_player()
    names = ("khudai", "dabu", "dhulai")
    spec["stages"] = [
        science.stage_entry(name, first) for name, first in zip(names, STAGE_UNITS, strict=True)
    ]
    for stage, scene in zip(spec["stages"], scenes, strict=False):
        if scene is not None:
            stage["scene"] = scene
    return spec


def test_a_stage_takes_its_own_scene_and_one_without_keeps_none() -> None:
    spec = staged_player(CARVED, None)
    checked = checked_spec("stage_player", spec)
    dumped = checked.model_dump(mode="json", by_alias=True)
    assert dumped == spec
    assert "scene" not in dumped["stages"][1]
    assert [path for path, _ in kit_scenes(checked)] == ["drawing", "stages[0].scene"]
    assert spec_problems("stage_player", spec, units(spec)) == []


def test_a_stage_s_own_scene_may_move_when_its_stage_is_shown_while_the_drawing_rests() -> None:
    spec = staged_player(CARVED, DIPS)
    assert [path for path, _ in kit_scenes(checked_spec("stage_player", spec))] == [
        "drawing",
        "stages[0].scene",
        "stages[1].scene",
    ]
    with pytest.raises(ValidationError, match="names no motion"):
        checked_spec("stage_player", {**spec, "drawing": DIPS})


def test_a_player_with_no_stage_scene_is_kept_as_before() -> None:
    spec = staged_player()
    dumped = checked_spec("stage_player", spec).model_dump(mode="json", by_alias=True)
    assert dumped == spec
    assert all("scene" not in stage for stage in dumped["stages"])


def test_the_last_stage_rests_on_the_player_s_drawing_and_names_no_scene_of_its_own() -> None:
    with pytest.raises(ValidationError, match=re.escape(REST_SCENE)):
        checked_spec("stage_player", staged_player(CARVED, None, STILL))


def test_a_stage_scene_drawn_by_hand_is_one_svg_held_to_the_bar_for_drawn_art() -> None:
    with pytest.raises(ValidationError, match=re.escape(DRAWN_STAGE.format(name="khudai"))):
        checked_spec("stage_player", staged_player({"tag": "g", "children": LINE_WORK["children"]}))
    spec = staged_player(LINE_WORK)
    assert checked_spec("stage_player", spec)
    assert spec_problems("stage_player", spec, units(spec)) == []
    painted = copy.deepcopy(LINE_WORK)
    painted["children"].append(
        {
            "tag": "rect",
            "attrs": {"x": "10", "y": "40", "width": "60", "height": "30", "fill": "var(--dye-indigo)"},
        }
    )
    painted["children"].append({"tag": "title", "children": ["A cloth lifted from the vat"]})
    refused = staged_player(painted)
    pointer = SCENE_POINTER.format(kind="stage_player")
    assert spec_problems("stage_player", refused, units(refused)) == [
        "the stage_player's drawing at stages[0].scene paints --dye-indigo by hand, which the kit's cloth part "
        f"draws textured, framed and named in a key; {pointer}"
    ]


def test_a_stage_scene_s_labels_cite_their_facts() -> None:
    spec = staged_player(CARVED)
    assert spec_problems("stage_player", spec, units(spec, frozenset({"u0606"}))) == [
        "the unit u0606, the label of the kit scene at stages[0].scene's block part, cites no fact: a kit "
        "part's label rests on the facts that state it"
    ]
