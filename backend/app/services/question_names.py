from __future__ import annotations

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from itertools import batched

from app.core.errors import AppError
from app.research.question_names import (
    NAMES_SCHEMA,
    NAMES_SYSTEM,
    QUESTIONS_PER_CALL,
    AskedQuestion,
    names_user,
    screened_questions,
)
from app.research.structured import StructuredModel, reply_object

__all__ = ["NamesScreen", "screen_names"]

logger = logging.getLogger(__name__)


@dataclass
class NamesScreen:
    screened: dict[str, str | None] = field(default_factory=dict)
    error: str | None = None


async def screen_names(model: StructuredModel, questions: Sequence[AskedQuestion]) -> NamesScreen:
    found = NamesScreen()
    for group in batched(questions, QUESTIONS_PER_CALL, strict=False):
        try:
            reply = await model(system=NAMES_SYSTEM, user=names_user(group), schema=NAMES_SCHEMA)
            found.screened |= screened_questions(group, reply_object(reply))
        except AppError as error:
            logger.warning("the names screen failed; its questions wait for the next night: %s", error)
            found.error = str(error)
            break
    return found
