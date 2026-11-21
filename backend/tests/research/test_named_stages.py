import uuid

from app.research.composition import StageOption
from app.research.crafts import CraftRef
from app.research.planning import PlanRequest
from app.research.sections import named_stage_ids

BIDRI = CraftRef(slug="Bidriware", name="Bidriware", path="/crafts/Bidriware")
STAGE_NAMES = (
    "Melting the alloy",
    "Mould making and casting",
    "Smoothing the cast article",
    "Temporary blackening with copper sulphate",
    "Drawing and engraving the design",
    "Silver inlay",
    "Levelling and sanding the inlaid surface",
    "Blackening in fort earth solution",
    "Drying",
    "Oiling and polishing",
)
STAGES = [
    StageOption(id=uuid.uuid5(uuid.NAMESPACE_URL, f"bidri/{n}"), ordinal=n, name=name)
    for n, name in enumerate(STAGE_NAMES, start=1)
]
MAKING_STAGES = "What are the stages of making a Bidri vessel, from casting the alloy to setting the silver?"


def asked(question: str) -> PlanRequest:
    return PlanRequest(question=question, mode="HYBRID", craft=BIDRI)


def ordinals(stage_ids: list[uuid.UUID]) -> list[int]:
    by_id = {stage.id: stage.ordinal for stage in STAGES}
    return [by_id[stage_id] for stage_id in stage_ids]


def test_a_question_from_one_stage_to_another_covers_every_stage_between() -> None:
    chosen = [STAGES[4].id, STAGES[7].id]
    assert ordinals(named_stage_ids(asked(MAKING_STAGES), STAGES, chosen)) == [1, 2, 3, 4, 5, 6, 8]


def test_the_stages_a_question_names_join_the_ones_the_composer_chose() -> None:
    question = "Which stages of making Bidriware need the silver inlay and the fort earth?"
    assert ordinals(named_stage_ids(asked(question), STAGES, [STAGES[8].id])) == [6, 7, 8, 9]


def test_a_question_that_does_not_ask_about_the_process_names_no_stage() -> None:
    question = "Why does the fort earth turn Bidriware black?"
    assert named_stage_ids(asked(question), STAGES, [STAGES[1].id]) == [STAGES[1].id]


def test_the_craft_s_own_name_and_process_words_name_no_stage() -> None:
    question = "What are the steps of making Bidriware?"
    assert named_stage_ids(asked(question), STAGES) == []
