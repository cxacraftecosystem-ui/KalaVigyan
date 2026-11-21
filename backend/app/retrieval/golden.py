from __future__ import annotations

import json
from functools import cache
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from app.core.errors import InvalidInput

from .evaluation import GoldenQuestion

__all__ = ["GOLDEN_FILE", "GOLDEN_VERSION", "golden_questions", "parse_golden"]

GOLDEN_FILE = Path(__file__).resolve().parents[1] / "data" / "eval" / "retrieval_questions.json"
GOLDEN_VERSION = 1


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


@cache
def golden_questions(path: Path = GOLDEN_FILE) -> tuple[GoldenQuestion, ...]:
    return parse_golden(json.loads(path.read_text(encoding="utf-8")))
