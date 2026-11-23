from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from pydantic import Field

from app.core.errors import InvalidInput

from .base import ContractModel
from .review_queue_parts import FactSource

__all__ = [
    "CHOOSE_PROCESS",
    "PLACED_STATUS",
    "REJECTED_STAGE_STATUS",
    "STAGE_CONCEPT_TYPE",
    "STAGE_FACTS_MAX",
    "ProcessStep",
    "StageFact",
    "StagePlace",
    "StagePlacing",
    "StageProcess",
    "stage_place",
]

STAGE_CONCEPT_TYPE = "PROCESS_STAGE"
PLACED_STATUS = "PLACED"
REJECTED_STAGE_STATUS = "REJECTED"
STAGE_FACTS_MAX = 12
CHOOSE_PROCESS = "Choose the process and the stage it follows before placing it."
NOT_IN_PROCESS = "The stage it follows is not in that process. Reload the queue."


class ProcessStep(ContractModel):
    id: uuid.UUID
    ordinal: int
    name: str


class StageProcess(ContractModel):
    id: uuid.UUID
    name: str
    stages: list[ProcessStep] = Field(min_length=1)


class StageFact(ContractModel):
    id: uuid.UUID
    text: str
    sources: list[FactSource]


class StagePlacing(ContractModel):
    name: str
    description: str | None
    processes: list[StageProcess] = Field(min_length=1)
    facts: list[StageFact]


@dataclass(frozen=True)
class StagePlace:
    ordinal: int
    moved: tuple[tuple[uuid.UUID, int], ...]


def stage_place(steps: Sequence[ProcessStep], after: uuid.UUID | None) -> StagePlace:
    ordered = sorted(steps, key=lambda step: step.ordinal)
    if not ordered:
        raise InvalidInput(CHOOSE_PROCESS)
    if after is None:
        ordinal = ordered[0].ordinal
    else:
        found = next((step for step in ordered if step.id == after), None)
        if found is None:
            raise InvalidInput(NOT_IN_PROCESS)
        ordinal = found.ordinal + 1
    moved = tuple((step.id, step.ordinal + 1) for step in ordered if step.ordinal >= ordinal)
    return StagePlace(ordinal=ordinal, moved=moved)
