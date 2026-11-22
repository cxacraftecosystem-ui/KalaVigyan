from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Annotated, Any, Literal

from pydantic import Field, ValidationError, field_validator

from app.core.errors import InvalidInput
from app.research.base import ContractModel

from .evaluation import FUSED, ORDERS, RERANKED

__all__ = [
    "EVAL_DIR",
    "FIRST_FLOORS_VERSION",
    "FLOORS_FILE",
    "FLOORS_VERSION",
    "FLOOR_DIGITS",
    "GENERATED",
    "HAND_WRITTEN",
    "JUDGE_MEAN",
    "MEAN_RECIPROCAL_RANK",
    "QUESTION_SETS",
    "RECALL_AT_5",
    "RELEASE_SAMPLE",
    "RUBRIC_MEAN",
    "AnswerFloors",
    "EvalFloors",
    "FloorCheck",
    "RetrievalFloors",
    "SetFloors",
    "broken",
    "eval_floors",
    "floor_checks",
    "floors_of_version_1",
    "parse_floors",
]

EVAL_DIR = Path(__file__).resolve().parents[1] / "data" / "eval"
FLOORS_FILE = EVAL_DIR / "floors.json"
FLOORS_VERSION = 2
FIRST_FLOORS_VERSION = 1
FLOOR_DIGITS = 4
HAND_WRITTEN = "handWritten"
GENERATED = "generated"
RELEASE_SAMPLE = "releaseSample"
QUESTION_SETS = (HAND_WRITTEN, GENERATED, RELEASE_SAMPLE)
RECALL_AT_5 = "recallAt5"
MEAN_RECIPROCAL_RANK = "meanReciprocalRank"
JUDGE_MEAN = "judgeMean"
RUBRIC_MEAN = "rubricMean"

Share = Annotated[float, Field(ge=0.0, le=1.0)]


class RetrievalFloors(ContractModel):
    recall_at5: Share | None = Field(default=None, alias=RECALL_AT_5)
    mean_reciprocal_rank: Share | None = Field(default=None, alias=MEAN_RECIPROCAL_RANK)

    def named(self) -> dict[str, float]:
        floors = {RECALL_AT_5: self.recall_at5, MEAN_RECIPROCAL_RANK: self.mean_reciprocal_rank}
        return {name: floor for name, floor in floors.items() if floor is not None}


class SetFloors(ContractModel):
    reranked: RetrievalFloors = Field(default_factory=RetrievalFloors)
    fused: RetrievalFloors = Field(default_factory=RetrievalFloors)

    def named(self, order: str) -> dict[str, float]:
        if order not in ORDERS:
            raise InvalidInput(f"Floors name only the orders {', '.join(ORDERS)}, not {order!r}")
        return (self.reranked if order == RERANKED else self.fused).named()


class AnswerFloors(ContractModel):
    judge_mean: Share | None = Field(default=None, alias=JUDGE_MEAN)
    rubric_mean: Share | None = Field(default=None, alias=RUBRIC_MEAN)

    def named(self) -> dict[str, float]:
        floors = {JUDGE_MEAN: self.judge_mean, RUBRIC_MEAN: self.rubric_mean}
        return {name: floor for name, floor in floors.items() if floor is not None}


class EvalFloors(ContractModel):
    version: Literal[2]
    about: str = ""
    retrieval: dict[str, SetFloors]
    answers: AnswerFloors

    @field_validator("retrieval")
    @classmethod
    def _known_sets(cls, sets: dict[str, SetFloors]) -> dict[str, SetFloors]:
        unknown = sorted(set(sets) - set(QUESTION_SETS))
        if unknown:
            raise ValueError(f"Floors name only the question sets {', '.join(QUESTION_SETS)}, not {unknown}")
        return sets

    def retrieval_floors(self, question_set: str, order: str) -> dict[str, float]:
        floors = self.retrieval.get(question_set, SetFloors())
        return floors.named(order)


@dataclass(frozen=True)
class FloorCheck:
    measure: str
    floor: float
    value: float | None

    @property
    def held(self) -> bool:
        return self.value is not None and round(self.value, FLOOR_DIGITS) >= self.floor

    def as_dict(self) -> dict[str, Any]:
        return {"measure": self.measure, "floor": self.floor, "value": self.value, "held": self.held}


def floor_checks(
    values: Mapping[str, float | None], floors: Mapping[str, float], *, prefix: str = ""
) -> tuple[FloorCheck, ...]:
    return tuple(FloorCheck(f"{prefix}{name}", floor, values.get(name)) for name, floor in floors.items())


def broken(checks: Sequence[FloorCheck]) -> list[FloorCheck]:
    return [check for check in checks if not check.held]


def floors_of_version_1(data: Mapping[str, Any]) -> dict[str, Any]:
    sets = data.get("retrieval")
    if not isinstance(sets, Mapping):
        raise InvalidInput("The version 1 evaluation floors name their retrieval floors per question set")
    return {
        **data,
        "version": FLOORS_VERSION,
        "retrieval": {name: {FUSED: floors} for name, floors in sets.items()},
    }


def parse_floors(data: Any) -> EvalFloors:
    if isinstance(data, dict) and data.get("version") == FIRST_FLOORS_VERSION:
        data = floors_of_version_1(data)
    if not isinstance(data, dict) or data.get("version") != FLOORS_VERSION:
        raise InvalidInput(
            f"The evaluation floors must be a version {FLOORS_VERSION} object "
            f"(version {FIRST_FLOORS_VERSION} is migrated)"
        )
    try:
        return EvalFloors.model_validate(data)
    except ValidationError as error:
        raise InvalidInput(f"The evaluation floors are malformed: {error}") from None


@cache
def eval_floors(path: Path = FLOORS_FILE) -> EvalFloors:
    return parse_floors(json.loads(path.read_text(encoding="utf-8")))
