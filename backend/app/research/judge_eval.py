from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal, Self

from pydantic import Field, model_validator

from .base import ContractModel
from .candidate_gates import COMPARISON_RELATIONS, Candidate, HeldFact
from .candidate_judge import JudgeAsk
from .vocabulary import Discipline

__all__ = [
    "ADDS",
    "JUDGE_CASES_VERSION",
    "NOT_ADDS",
    "DuplicateCase",
    "FloorCheck",
    "JudgeCases",
    "JudgeFloors",
    "JudgeScores",
    "NoveltyCase",
    "duplicate_asks",
    "duplicate_scores",
    "floor_checks",
    "novelty_asks",
    "novelty_scores",
]

JUDGE_CASES_VERSION = 1
ADDS, NOT_ADDS = NOVELTY_LABELS = ("ADDS", "NOT_ADDS")
SAME, DIFFERS, DISTINCT = COMPARISON_RELATIONS
HELD_SIMILARITY = 0.9
DIGITS = 4

Relation = Literal[*COMPARISON_RELATIONS]
NoveltyLabel = Literal[*NOVELTY_LABELS]


class DuplicateCase(ContractModel):
    key: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9-]+$")
    field: Discipline
    candidate: str = Field(min_length=20)
    held: str = Field(min_length=20)
    label: Relation
    why: str = Field(min_length=1)
    origin: str = Field(min_length=1)


class NoveltyCase(ContractModel):
    key: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9-]+$")
    field: Discipline
    candidate: str = Field(min_length=20)
    held: list[str] = Field(min_length=1)
    label: NoveltyLabel
    why: str = Field(min_length=1)
    origin: str = Field(min_length=1)


class JudgeFloors(ContractModel):
    duplicate_accuracy: float = Field(ge=0, le=1)
    distinct_kept: float = Field(ge=0, le=1)
    novelty_accuracy: float = Field(ge=0, le=1)


class JudgeCases(ContractModel):
    version: Literal[1] = JUDGE_CASES_VERSION
    floors: JudgeFloors
    duplicate: list[DuplicateCase] = Field(min_length=1)
    novelty: list[NoveltyCase] = Field(min_length=1)

    @model_validator(mode="after")
    def _keys_once(self) -> Self:
        keys = [case.key for case in [*self.duplicate, *self.novelty]]
        if len(set(keys)) != len(keys):
            raise ValueError("every case has its own key")
        return self


@dataclass(frozen=True)
class JudgeScores:
    measures: Mapping[str, float | None]
    wrong: Sequence[Mapping[str, str]] = field(default_factory=tuple)


@dataclass(frozen=True)
class FloorCheck:
    measure: str
    value: float | None
    floor: float

    @property
    def held(self) -> bool:
        return self.value is not None and round(self.value, DIGITS) >= self.floor


def duplicate_asks(cases: Sequence[DuplicateCase]) -> list[JudgeAsk]:
    return [
        JudgeAsk(
            Candidate(ref=case.key, statement=case.candidate, field=case.field), (_held(case.key, case.held),)
        )
        for case in cases
    ]


def novelty_asks(cases: Sequence[NoveltyCase]) -> list[JudgeAsk]:
    return [
        JudgeAsk(
            Candidate(ref=case.key, statement=case.candidate, field=case.field),
            tuple(_held(f"{case.key}-{at}", text) for at, text in enumerate(case.held)),
        )
        for case in cases
    ]


def duplicate_scores(cases: Sequence[DuplicateCase], found: Mapping[str, str]) -> JudgeScores:
    distinct = [case for case in cases if case.label == DISTINCT]
    return JudgeScores(
        measures={
            "duplicate.accuracy": _share(cases, found),
            "duplicate.distinctKept": _share(distinct, found),
        },
        wrong=_wrong(cases, found),
    )


def novelty_scores(cases: Sequence[NoveltyCase], found: Mapping[str, bool]) -> JudgeScores:
    said = {key: ADDS if adds else NOT_ADDS for key, adds in found.items()}
    return JudgeScores(measures={"novelty.accuracy": _share(cases, said)}, wrong=_wrong(cases, said))


def floor_checks(measures: Mapping[str, float | None], floors: JudgeFloors) -> list[FloorCheck]:
    return [
        FloorCheck("duplicate.accuracy", measures.get("duplicate.accuracy"), floors.duplicate_accuracy),
        FloorCheck("duplicate.distinctKept", measures.get("duplicate.distinctKept"), floors.distinct_kept),
        FloorCheck("novelty.accuracy", measures.get("novelty.accuracy"), floors.novelty_accuracy),
    ]


def _held(key: str, text: str) -> HeldFact:
    return HeldFact(
        id=uuid.uuid5(uuid.NAMESPACE_URL, f"judge-eval/{key}"), text=text, similarity=HELD_SIMILARITY
    )


def _share(cases: Sequence[DuplicateCase | NoveltyCase], found: Mapping[str, str]) -> float | None:
    if not cases:
        return None
    right = sum(1 for case in cases if found.get(case.key) == case.label)
    return round(right / len(cases), DIGITS)


def _wrong(
    cases: Sequence[DuplicateCase | NoveltyCase], found: Mapping[str, str]
) -> tuple[dict[str, str], ...]:
    return tuple(
        {"key": case.key, "label": case.label, "judged": found.get(case.key, "UNJUDGED")}
        for case in cases
        if found.get(case.key) != case.label
    )
