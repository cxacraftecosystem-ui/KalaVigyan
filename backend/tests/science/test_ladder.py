import dataclasses
import uuid

from app.research.crafts import CraftRef
from app.science.ladder import ladder_problems, ladder_stage_options, process_ladder
from app.science.process_view import craft_process
from app.science.records import ProcessRecords

from .golden_process import KUT, PA, PROCESS_ID, RED, STAGE_CLAIMS, golden_records, known_claim, stage_id

KUT_REACTION = uuid.UUID("d9643f49-fefc-5e3a-ad08-a5ae499a4161")
RED_REACTION = uuid.UUID("26229ecd-184c-5adf-86d0-b45c56394f27")
KUT_PASTE = uuid.UUID("6a3e5cb8-ef2e-501f-a7f8-d7d0772d56e4")
MADDER = uuid.UUID("a96fc53e-88ae-5f99-acd3-09346d9a67ea")


def ladder(*stages: str):
    built = process_ladder(golden_records(), block_id="s1.b1", stage_ids=[stage_id(s) for s in stages])
    assert built is not None
    return built


def test_the_offered_stages_are_the_stored_stages_with_a_fact_in_ordinal_order() -> None:
    options = ladder_stage_options(golden_records())
    assert [(option.id, option.ordinal, option.name) for option in options] == [
        (stage_id(KUT), 5, "Kut (iron-black printing)"),
        (stage_id(PA), 6, "Pa (alum mordant printing for red)"),
        (stage_id(RED), 11, "Red dyeing (rang) with madder or alizarin"),
    ]


def test_a_ladder_takes_its_stages_claims_conditions_and_reactions_from_the_stored_rows() -> None:
    built = ladder(RED, KUT)
    assert (built.id, built.process_id, built.craft.slug) == ("s1.b1", PROCESS_ID, "Kutch-Ajrakh")
    kut, red = built.stages
    assert [(stage.ordinal, stage.stage_type, stage.level) for stage in built.stages] == [
        (5, "PRINT", "PROVISIONAL"),
        (11, "DYE", "PROVISIONAL"),
    ]
    assert [sentence.id for stage in built.stages for sentence in stage.sentences] == ["s1.b1.1", "s1.b1.2"]
    assert kut.sentences[0].text == known_claim(STAGE_CLAIMS[KUT]).text
    assert red.sentences[0].text == known_claim(STAGE_CLAIMS[RED]).text
    assert [(c.label, c.stated) for c in kut.conditions] == [
        ("Fermenting the iron paste", "ten to fifteen days")
    ]
    assert [(c.label, c.stated) for c in red.conditions] == [("Red dye bath", "up to four hours")]
    assert (kut.reaction_ids, red.reaction_ids) == ([KUT_REACTION], [RED_REACTION])
    assert [m.material_id for m in kut.materials] == [KUT_PASTE]
    assert [m.material_id for m in red.materials] == [MADDER]
    assert ladder_problems(built, golden_records()) == []


def test_stages_outside_the_stored_rows_build_no_ladder() -> None:
    assert process_ladder(golden_records(), block_id="s1.b1", stage_ids=[uuid.uuid4()]) is None


def test_a_ladder_with_a_stage_not_in_the_stored_rows_is_refused() -> None:
    built = ladder(KUT)
    stranger = uuid.UUID("0f0e0d0c-0b0a-4908-8706-050403020100")
    forged = built.model_copy(update={"stages": [built.stages[0].model_copy(update={"stage_id": stranger})]})
    assert ladder_problems(forged, golden_records()) == [
        f"stage {stranger} is not a stored stage of process {PROCESS_ID}"
    ]


def test_a_ladder_stage_that_states_something_its_claims_do_not_is_refused() -> None:
    built = ladder(KUT)
    stage = built.stages[0]
    sentence = stage.sentences[0].model_copy(update={"text": "Kut is printed at dawn."})
    forged = built.model_copy(update={"stages": [stage.model_copy(update={"sentences": [sentence]})]})
    assert ladder_problems(forged, golden_records()) == [
        f"stage {stage_id(KUT)} sentence s1.b1.1 is not one of its stored claims"
    ]


def test_a_ladder_condition_or_reaction_that_is_not_stored_for_its_stage_is_refused() -> None:
    built = ladder(KUT)
    stage = built.stages[0]
    condition = stage.conditions[0].model_copy(update={"stated": "two weeks or more"})
    forged_stage = stage.model_copy(update={"conditions": [condition], "reaction_ids": [RED_REACTION]})
    forged = built.model_copy(update={"stages": [forged_stage]})
    assert ladder_problems(forged, golden_records()) == [
        f"stage {stage_id(KUT)} condition 'Fermenting the iron paste' is not stored for it",
        f"stage {stage_id(KUT)} reaction {RED_REACTION} is not stored for it",
    ]


def test_a_ladder_for_another_craft_is_refused() -> None:
    other = CraftRef(
        slug="Bagru-Hand-Block-Print", name="Bagru Hand Block Print", path="/crafts/Bagru-Hand-Block-Print"
    )
    forged = ladder(KUT).model_copy(update={"craft": other})
    assert ladder_problems(forged, golden_records()) == [
        "ladder s1.b1 is for Bagru-Hand-Block-Print, not Kutch-Ajrakh"
    ]


def with_pa_unordered() -> ProcessRecords:
    records = golden_records()
    stages = tuple(
        dataclasses.replace(stage, ordered=False) if stage.id == stage_id(PA) else stage
        for stage in records.stages
    )
    return dataclasses.replace(records, stages=stages)


def test_a_stage_no_source_orders_is_never_offered_to_a_ladder_and_shown_unnumbered_in_one() -> None:
    records = with_pa_unordered()
    assert [option.id for option in ladder_stage_options(records)] == [stage_id(KUT), stage_id(RED)]
    built = process_ladder(records, block_id="s1.b1", stage_ids=[stage_id(KUT), stage_id(PA), stage_id(RED)])
    assert built is not None
    assert [(stage.stage_id, stage.unnumbered) for stage in built.stages] == [
        (stage_id(KUT), None),
        (stage_id(PA), True),
        (stage_id(RED), None),
    ]
    assert ladder_problems(built, records) == []


def test_a_stored_ladder_numbering_a_stage_now_unordered_is_refused() -> None:
    stored = ladder(KUT, PA)
    problems = ladder_problems(stored, with_pa_unordered())
    assert problems == [f"stage {stage_id(PA)} has no order a source states, so no ladder numbers it"]


def test_the_process_route_marks_only_an_unordered_stage() -> None:
    (process,) = craft_process(with_pa_unordered()).processes
    shown = {stage.id: stage.model_dump(mode="json", by_alias=True) for stage in process.stages}
    assert shown[stage_id(PA)]["ordered"] is False
    assert "ordered" not in shown[stage_id(KUT)]
