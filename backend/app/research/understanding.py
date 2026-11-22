from __future__ import annotations

from typing import Literal, Protocol, Self, runtime_checkable

from pydantic import Field, model_validator

from app.core.errors import InvalidInput
from app.models.enums import DISCIPLINES

from .base import ContractModel, absent, empty
from .blocks_people import ExpertSeat
from .crafts import COMPARED_CRAFTS_MAX, MAX_CANDIDATES, QUESTION_MAX_CHARS, SLUG_MAX_CHARS, CraftRef
from .depth import depth_policy
from .explainer import UNDERSTANDING_BASES, UnderstandingBasis, Understood
from .vocabulary import CANONICAL_LANGUAGE, AnswerLanguage, Depth, Discipline

__all__ = [
    "ENGLISH_QUESTION_MIN_CHARS",
    "REFUSAL_MAX_CHARS",
    "UNDERSTANDING_BASES",
    "UNDERSTANDING_SCHEMA_VERSION",
    "UnderstandAsk",
    "Understander",
    "Understanding",
    "UnknownCraft",
]

UNDERSTANDING_SCHEMA_VERSION = 1
REFUSAL_MAX_CHARS = 500
ENGLISH_QUESTION_MIN_CHARS = 2


class UnknownCraft(InvalidInput):
    def __init__(self, slug: str) -> None:
        super().__init__(f"No craft has the slug {slug!r}")
        self.slug = slug


class UnderstandAsk(ContractModel):
    question: str = Field(min_length=1, max_length=QUESTION_MAX_CHARS)
    depth: Depth
    language: AnswerLanguage = CANONICAL_LANGUAGE
    craft_slug: str | None = Field(default=None, min_length=1, max_length=SLUG_MAX_CHARS)
    any_craft: bool = False
    role: str | None = None

    @model_validator(mode="after")
    def _one_craft_or_any(self) -> Self:
        if self.any_craft and self.craft_slug is not None:
            raise ValueError("a question names one craft or any craft, not both")
        return self


class Understanding(ContractModel):
    schema_version: Literal[1] = UNDERSTANDING_SCHEMA_VERSION
    craft: CraftRef | None
    candidates: list[CraftRef] = Field(max_length=MAX_CANDIDATES)
    compared: list[CraftRef] = Field(default_factory=list, max_length=COMPARED_CRAFTS_MAX, exclude_if=empty)
    disciplines: list[Discipline] = Field(max_length=len(DISCIPLINES))
    asked: list[Discipline] = Field(default_factory=list, max_length=len(DISCIPLINES), exclude_if=empty)
    seats: list[ExpertSeat]
    depth: Depth
    language: AnswerLanguage
    english_question: str | None = Field(
        default=None, min_length=ENGLISH_QUESTION_MIN_CHARS, max_length=QUESTION_MAX_CHARS, exclude_if=absent
    )
    basis: UnderstandingBasis
    refusal: str | None = Field(default=None, min_length=1, max_length=REFUSAL_MAX_CHARS, exclude_if=absent)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        slugs = [
            craft.slug for craft in (*([self.craft] if self.craft else []), *self.compared, *self.candidates)
        ]
        if len(set(slugs)) != len(slugs):
            raise ValueError("a craft is chosen, compared or offered, once")
        if self.compared and (self.craft is None or self.basis != "MODEL"):
            raise ValueError("a comparison is a model understanding that chose a craft to lead it")
        if len(set(self.disciplines)) != len(self.disciplines) or len(set(self.seats)) != len(self.seats):
            raise ValueError("each discipline and each seat is listed once")
        if len(set(self.asked)) != len(self.asked) or not set(self.asked) <= set(self.disciplines):
            raise ValueError("the asked fields are listed once, each among the answer's fields")
        if len(self.seats) > depth_policy(self.depth).max_experts:
            raise ValueError(f"{self.depth} seats at most {depth_policy(self.depth).max_experts} experts")
        if self.basis == "MODEL" and not self.disciplines:
            raise ValueError("a model understanding names the fields the question touches")
        if self.refusal is not None and self.basis != "RESOLVER":
            raise ValueError("a refused model call leaves the resolver's understanding")
        return self

    def understood(self) -> Understood:
        return Understood(
            crafts=[self.craft, *self.compared] if self.craft else [],
            candidates=self.candidates,
            depth=self.depth,
            language=self.language,
            basis=self.basis,
        )


@runtime_checkable
class Understander(Protocol):
    async def understand(self, ask: UnderstandAsk) -> Understanding: ...
