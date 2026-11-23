import uuid

import pytest
from pydantic import TypeAdapter

from app.core.errors import InvalidInput
from app.research.review_queue import QueueApproval, QueueItem
from app.research.review_queue_stages import ProcessStep, stage_place


def step(name: str, ordinal: int) -> ProcessStep:
    return ProcessStep(id=uuid.uuid5(uuid.NAMESPACE_URL, f"stage/{name}"), ordinal=ordinal, name=name)


SOAK, PRINT, WASH = step("soak", 1), step("print", 2), step("wash", 3)


def test_a_stage_placed_after_another_takes_the_next_ordinal_and_moves_the_rest_down() -> None:
    place = stage_place([WASH, SOAK, PRINT], PRINT.id)
    assert (place.ordinal, place.moved) == (3, ((WASH.id, 4),))


def test_a_stage_placed_first_takes_the_first_ordinal_and_moves_every_stage() -> None:
    place = stage_place([SOAK, PRINT, WASH], None)
    assert (place.ordinal, place.moved) == (1, ((SOAK.id, 2), (PRINT.id, 3), (WASH.id, 4)))


def test_a_stage_placed_last_moves_nothing() -> None:
    assert stage_place([SOAK, PRINT, WASH], WASH.id).moved == ()


def test_a_gap_in_the_ordinals_still_moves_every_later_stage_by_one() -> None:
    first, later = step("first", 0), step("later", 5)
    place = stage_place([first, step("second", 2), later], first.id)
    assert (place.ordinal, [ordinal for _, ordinal in place.moved]) == (1, [3, 6])


def test_a_stage_named_outside_the_process_is_refused() -> None:
    with pytest.raises(InvalidInput, match="not in that process"):
        stage_place([SOAK, PRINT], WASH.id)
    with pytest.raises(InvalidInput, match="Choose the process"):
        stage_place([], None)


def test_an_approval_names_the_process_and_the_stage_it_follows() -> None:
    approval = QueueApproval.model_validate({"processId": str(SOAK.id), "afterStageId": str(PRINT.id)})
    assert (approval.process_id, approval.after_stage_id) == (SOAK.id, PRINT.id)


def test_a_stage_item_reads_with_its_processes_and_facts() -> None:
    item = TypeAdapter(QueueItem).validate_python(
        {
            "kind": "STAGES",
            "id": str(SOAK.id),
            "origin": "RESEARCH",
            "submittedAt": "2026-11-23T09:00:00Z",
            "craft": {"slug": "Kutch-Ajrakh", "name": "Kutch Ajrakh", "path": "/crafts/Kutch-Ajrakh"},
            "stage": {
                "name": "Drying in the sun",
                "description": None,
                "processes": [
                    {"id": str(WASH.id), "name": "Process", "stages": [PRINT.model_dump(by_alias=True)]}
                ],
                "facts": [],
            },
        }
    )
    assert item.kind == "STAGES"
    assert [process.stages[0].name for process in item.stage.processes] == ["print"]
