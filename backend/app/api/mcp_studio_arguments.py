from __future__ import annotations

import uuid
from collections.abc import Mapping
from typing import Any, Literal, Self

from pydantic import Field, ValidationError, model_validator

from app.core.errors import InvalidInput
from app.core.roles import Capability, can
from app.models import User
from app.research.knowledge_writes import FactProposal
from app.research.monograph_document import SUBJECT_KINDS
from app.research.page_drafts import (
    DRAFT_PARTS,
    SUPPLIED_PER_DRAFT_MAX,
    DraftAddition,
    PageLists,
)
from app.research.page_proposals import (
    COMPONENTS_MAX,
    FACTS_MAX,
    NOTE_MAX_CHARS,
    PICTURES_MAX,
    SLUG_PATTERN,
    STRUCTURE_MAX,
    PageComponent,
    PageLayoutPart,
    PagePicture,
)
from app.research.structure_proposals import StructureProposal
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
from .mcp_tool_base import ToolContext

__all__ = [
    "AddToDraft",
    "CreateDraft",
    "DraftRef",
    "RemoveFromDraft",
    "StudioArguments",
    "SupplySourceArguments",
    "contributor",
]

NEEDS_CONTRIBUTOR = (
    "{tool} needs an account of Researcher or above; this account cannot contribute pages or sources."
)
DRAFT_ID = "The draft's id, from create_draft"


class StudioArguments(SnakeBodyArguments):
    @classmethod
    def reshaped(cls, data: Mapping[str, Any]) -> tuple[dict[str, Any], tuple[str, ...]]:
        aliases = frozenset().union(*(model_aliases(info.annotation) for info in cls.model_fields.values()))
        moved = dict(data)
        return moved, camel_keys(moved, aliases)


def contributor(context: ToolContext, tool: str) -> User:
    user = context.user
    if user is None or not can(user, Capability.PROPOSE_KNOWLEDGE):
        raise InvalidInput(NEEDS_CONTRIBUTOR.format(tool=tool))
    return user


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
    draft_id: uuid.UUID | None = Field(default=None, description="A draft to attach the source to at once")

    @model_validator(mode="after")
    def _one_way_in(self) -> Self:
        self.supplied()
        return self

    def supplied(self) -> SupplySource:
        try:
            return SupplySource.model_validate(self.model_dump(exclude={"draft_id"}))
        except ValidationError as refused:
            raise ValueError(problems(refused)) from None


class CreateDraft(StudioArguments):
    subject_kind: Literal[*SUBJECT_KINDS] = Field(description="craft, family or category")
    slug: str = Field(min_length=1, max_length=200, pattern=SLUG_PATTERN, description="The page's slug")
    lists: PageLists | None = Field(
        default=None,
        description=(
            "The page's own lists, derived first: mechanisms, ambiguous_terms and the signature fact "
            "(fact:N of this draft, or a stored fact's id); the preview checks them"
        ),
    )
    note: str | None = Field(default=None, min_length=1, max_length=NOTE_MAX_CHARS)


class AddToDraft(StudioArguments):
    draft_id: uuid.UUID = Field(description=DRAFT_ID)
    facts: list[FactProposal] = Field(
        default_factory=list, max_length=FACTS_MAX, description="Facts as propose_fact takes them"
    )
    structure: list[StructureProposal] = Field(
        default_factory=list,
        max_length=STRUCTURE_MAX,
        description="Structure items as propose_structure takes them",
    )
    components: list[PageComponent] = Field(
        default_factory=list,
        max_length=COMPONENTS_MAX,
        description="Finished components, each {proposal, cites}; cites names the draft's facts as fact:0 and on",
    )
    layout: PageLayoutPart | None = Field(default=None, description="The page's layout; replaces the draft's")
    pictures: list[PagePicture] = Field(
        default_factory=list,
        max_length=PICTURES_MAX,
        description="Pictures: {contribution_id} for one given with give_image, or a new {claim_ids, declaration}",
    )
    supplied_sources: list[uuid.UUID] = Field(
        default_factory=list, max_length=SUPPLIED_PER_DRAFT_MAX, description="Ids from supply_source"
    )
    lists: PageLists | None = Field(default=None, description="Replaces the draft's lists")
    note: str | None = Field(default=None, min_length=1, max_length=NOTE_MAX_CHARS)

    @model_validator(mode="after")
    def _adds_something(self) -> Self:
        self.addition()
        return self

    def addition(self) -> DraftAddition:
        try:
            return DraftAddition.model_validate(self.model_dump(exclude={"draft_id"}))
        except ValidationError as refused:
            raise ValueError(problems(refused)) from None


class RemoveFromDraft(StudioArguments):
    draft_id: uuid.UUID = Field(description=DRAFT_ID)
    part: Literal[*DRAFT_PARTS] = Field(description=f"One of {', '.join(DRAFT_PARTS)}")
    index: int = Field(ge=0, description="The part's index, as get_draft lists it")


class DraftRef(StudioArguments):
    draft_id: uuid.UUID = Field(description=DRAFT_ID)
