from __future__ import annotations

import json
import uuid
from datetime import datetime
from functools import cache
from pathlib import Path
from typing import Any, Literal, Self

from pydantic import Field, ValidationError, field_validator, model_validator

from app.core.errors import InvalidInput
from app.research.base import ContractModel

from .eval_floors import EVAL_DIR
from .evaluation import GoldenQuestion

__all__ = [
    "GENERATED_FILE",
    "GENERATED_SCHEMA_FILE",
    "GENERATED_VERSION",
    "GOLDEN_FILE",
    "GOLDEN_VERSION",
    "LANGUAGE_CODE",
    "GeneratedQuestion",
    "GeneratedSet",
    "generated_schema_text",
    "generated_set",
    "golden_questions",
    "parse_generated",
    "parse_golden",
]

GOLDEN_FILE = EVAL_DIR / "retrieval_questions.json"
GOLDEN_VERSION = 1
GENERATED_FILE = EVAL_DIR / "generated" / "retrieval_questions.json"
GENERATED_SCHEMA_FILE = EVAL_DIR / "generated" / "retrieval_questions.schema.json"
GENERATED_VERSION = 1
LANGUAGE_CODE = r"^[a-z]{2,3}$"


class GeneratedQuestion(GoldenQuestion):
    craft_slug: str = Field(min_length=1, max_length=200)
    fact: uuid.UUID
    language: str = Field(pattern=LANGUAGE_CODE)
    rejected: tuple[uuid.UUID, ...] = ()

    @model_validator(mode="after")
    def _one_fact_of_claim_ids(self) -> Self:
        if len(self.facts) != 1:
            raise ValueError("A generated question expects one fact, with its restatements")
        try:
            claims = {uuid.UUID(name) for name in self.facts[0]}
        except ValueError:
            raise ValueError("A generated question names its claims by id") from None
        if self.fact not in claims:
            raise ValueError(
                "A generated question lists the fact it was written from among its expected claims"
            )
        if claims & set(self.rejected):
            raise ValueError("A claim the judge rejected is never expected")
        return self


class GeneratedSet(ContractModel):
    version: Literal[1]
    revision: int = Field(ge=1)
    generated_at: datetime
    model: str | None = Field(default=None, max_length=120)
    seed: int
    facts_per_craft: int = Field(ge=1)
    questions: tuple[GeneratedQuestion, ...]

    @field_validator("questions")
    @classmethod
    def _keys_of_their_own(cls, questions: tuple[GeneratedQuestion, ...]) -> tuple[GeneratedQuestion, ...]:
        keys = [question.key for question in questions]
        if len(set(keys)) != len(keys):
            raise ValueError("Each generated question needs a key of its own")
        return questions


def parse_golden(data: Any) -> tuple[GoldenQuestion, ...]:
    if not isinstance(data, dict) or data.get("version") != GOLDEN_VERSION:
        raise InvalidInput(f"The retrieval questions must be a version {GOLDEN_VERSION} object")
    try:
        questions = tuple(GoldenQuestion.model_validate(item) for item in data.get("questions", ()))
    except ValidationError as error:
        raise InvalidInput(f"A retrieval question is malformed: {error}") from None
    keys = [question.key for question in questions]
    if len(set(keys)) != len(keys):
        raise InvalidInput("Each retrieval question needs a key of its own")
    return questions


def parse_generated(data: Any) -> GeneratedSet:
    if not isinstance(data, dict) or data.get("version") != GENERATED_VERSION:
        raise InvalidInput(f"The generated retrieval questions must be a version {GENERATED_VERSION} object")
    try:
        return GeneratedSet.model_validate(data)
    except ValidationError as error:
        raise InvalidInput(f"The generated retrieval questions are malformed: {error}") from None


@cache
def golden_questions(path: Path = GOLDEN_FILE) -> tuple[GoldenQuestion, ...]:
    return parse_golden(json.loads(path.read_text(encoding="utf-8")))


def generated_set(path: Path = GENERATED_FILE) -> GeneratedSet | None:
    if not path.is_file():
        return None
    return parse_generated(json.loads(path.read_text(encoding="utf-8")))


def generated_schema_text() -> str:
    return json.dumps(GeneratedSet.model_json_schema(by_alias=True), indent=2, ensure_ascii=False) + "\n"
