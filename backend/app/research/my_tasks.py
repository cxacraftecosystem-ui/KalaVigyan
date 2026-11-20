from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal

from pydantic import Field

from app.models.open_work import RESERVATION_ENDINGS

from .base import ContractModel
from .contribution_queue import ProposalTicket
from .open_work import OPEN_WORK_SCHEMA_VERSION, TASK_KEY_MAX_CHARS, OpenTask, TaskHold
from .trust_tiers import TrustTier

__all__ = [
    "CLAIMS_PER_CALL_MAX",
    "COMPLETED_SHOWN_MAX",
    "COMPLETED_WINDOW",
    "OUTCOMES_SHOWN_MAX",
    "EndedTask",
    "HeldTask",
    "MyTasks",
    "RefusedClaim",
    "TaskClaims",
]

CLAIMS_PER_CALL_MAX = 10
COMPLETED_SHOWN_MAX = 50
OUTCOMES_SHOWN_MAX = 20
COMPLETED_WINDOW = timedelta(days=30)

Ending = Literal[*RESERVATION_ENDINGS]


class RefusedClaim(ContractModel):
    task_key: str = Field(min_length=1, max_length=TASK_KEY_MAX_CHARS)
    problem: str


class TaskClaims(ContractModel):
    schema_version: Literal[1] = OPEN_WORK_SCHEMA_VERSION
    held: list[TaskHold]
    refused: list[RefusedClaim]
    tier: TrustTier
    holding: int = Field(ge=0)
    holding_max: int = Field(ge=1)
    message: str
    notices: list[str] = Field(default_factory=list)


class HeldTask(ContractModel):
    task_key: str = Field(min_length=1, max_length=TASK_KEY_MAX_CHARS)
    reserved_until: datetime
    task: OpenTask | None


class EndedTask(ContractModel):
    task_key: str = Field(min_length=1, max_length=TASK_KEY_MAX_CHARS)
    ending: Ending
    ended_at: datetime


class MyTasks(ContractModel):
    schema_version: Literal[1] = OPEN_WORK_SCHEMA_VERSION
    tier: TrustTier
    holding: int = Field(ge=0)
    holding_max: int = Field(ge=1)
    reservation_minutes: int = Field(ge=1)
    claimed: list[HeldTask]
    completed: list[EndedTask]
    outcomes: list[ProposalTicket]
