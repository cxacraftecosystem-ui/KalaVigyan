from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Any, Literal, Self

from pydantic import Field, ValidationError, model_validator

from app.research.supplied_sources import (
    PASSAGES_MAX,
    SUPPLIED_TEXT_MAX_CHARS,
    UPLOAD_KINDS,
    SourceAccess,
    SourceIdentity,
    SuppliedPassage,
    SupplySource,
)

from .mcp_argument_names import SnakeBodyArguments, camel_keys, model_aliases, problems

__all__ = ["STUDIO_DOES", "StudioArguments", "SupplySourceArguments"]

STUDIO_DOES = "contribute pages or sources"


class StudioArguments(SnakeBodyArguments):
    @classmethod
    def reshaped(cls, data: Mapping[str, Any]) -> tuple[dict[str, Any], tuple[str, ...]]:
        aliases = frozenset().union(*(model_aliases(info.annotation) for info in cls.model_fields.values()))
        moved = dict(data)
        return moved, camel_keys(moved, aliases)


class SupplySourceArguments(StudioArguments):
    identity: SourceIdentity = Field(
        description=(
            "doi, isbn or url (at least one), title, authors, year, publisher, kind (PAPER, BOOK, BOOK_CHAPTER, "
            "WEB_PAGE, ENCYCLOPEDIA, DATASET, GI_JOURNAL, GOVERNMENT_REPORT or OTHER) and language, as the "
            "source states them; the scholarly indexes confirm it"
        )
    )
    access: SourceAccess = Field(
        description=(
            "how you read it (SUBSCRIPTION, INSTITUTION, OWN_COPY, ARCHIVE or BLOCKED_SITE), accessed_on "
            "(YYYY-MM-DD) and an optional note such as the library or database"
        )
    )
    licence: str | None = Field(
        default=None, min_length=2, max_length=200, description="The source's own licence"
    )
    passages: list[SuppliedPassage] = Field(
        default_factory=list,
        max_length=PASSAGES_MAX,
        description="The passages you will quote, each {text, locator}, copied verbatim with where they stand",
    )
    text: str | None = Field(
        default=None,
        max_length=SUPPLIED_TEXT_MAX_CHARS,
        description="Or the whole document as plain text (200 characters and up)",
    )
    upload: Literal[*UPLOAD_KINDS] | None = Field(
        default=None, description="Or pdf or text: a private upload slot is returned for the file"
    )
    draft_id: uuid.UUID | None = Field(
        default=None, description="A draft from edit_draft to attach the source to at once"
    )

    @model_validator(mode="after")
    def _one_way_in(self) -> Self:
        self.supplied()
        return self

    def supplied(self) -> SupplySource:
        try:
            return SupplySource.model_validate(self.model_dump(exclude={"draft_id"}))
        except ValidationError as refused:
            raise ValueError(problems(refused)) from None
