from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import Field

from .base import ContractModel
from .crafts import SLUG_MAX_CHARS
from .open_work import OpenTask, TaskSubject

__all__ = [
    "STEWARDSHIP_SCHEMA_VERSION",
    "STEWARD_CRAFTS_MAX",
    "MyCrafts",
    "StewardPackage",
    "Stewardship",
]

STEWARDSHIP_SCHEMA_VERSION = 1
STEWARD_CRAFTS_MAX = 10


class StewardPackage(ContractModel):
    craft: TaskSubject
    adopted_at: datetime
    seen_at: datetime | None
    stewards: int = Field(ge=1)
    new_tasks: list[OpenTask]
    tasks: list[OpenTask]
    total: int = Field(ge=0)


class MyCrafts(ContractModel):
    schema_version: Literal[1] = STEWARDSHIP_SCHEMA_VERSION
    crafts: list[StewardPackage]
    adopted: int = Field(ge=0)
    adopted_max: int = Field(ge=1)
    message: str


class Stewardship(ContractModel):
    schema_version: Literal[1] = STEWARDSHIP_SCHEMA_VERSION
    craft_slug: str = Field(min_length=1, max_length=SLUG_MAX_CHARS)
    adopted: bool
    message: str
