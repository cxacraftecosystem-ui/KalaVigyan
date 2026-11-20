from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Literal, Self

from pydantic import Field, model_validator

from .base import ContractModel

__all__ = [
    "LEDGER_DAYS_DEFAULT",
    "LEDGER_DAYS_MAX",
    "CostLedger",
    "LedgerDay",
    "LedgerRange",
    "LedgerTotal",
]

LEDGER_SCHEMA_VERSION = 1
LEDGER_DAYS_DEFAULT = 7
LEDGER_DAYS_MAX = 92


class LedgerRange(ContractModel):
    day_from: date
    day_to: date

    @model_validator(mode="after")
    def _forward_and_bounded(self) -> Self:
        if self.day_to < self.day_from:
            raise ValueError("the range ends before it starts")
        if self.day_to - self.day_from >= timedelta(days=LEDGER_DAYS_MAX):
            raise ValueError(f"a ledger covers at most {LEDGER_DAYS_MAX} days")
        return self


class LedgerDay(ContractModel):
    day: date
    user_id: uuid.UUID | None
    name: str | None
    role: str | None
    proposals: int = Field(ge=0)
    calls: int = Field(ge=0)
    judge_calls: int = Field(ge=0)
    embed_calls: int = Field(ge=0)
    failures: int = Field(ge=0)
    cost_usd: float = Field(ge=0.0)


class LedgerTotal(ContractModel):
    user_id: uuid.UUID | None
    name: str | None
    proposals: int = Field(ge=0)
    calls: int = Field(ge=0)
    cost_usd: float = Field(ge=0.0)


class CostLedger(ContractModel):
    schema_version: Literal[1] = LEDGER_SCHEMA_VERSION
    day_from: date
    day_to: date
    time_zone: str
    days: list[LedgerDay]
    accounts: list[LedgerTotal]
    calls: int = Field(ge=0)
    cost_usd: float = Field(ge=0.0)
