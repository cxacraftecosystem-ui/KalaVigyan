from __future__ import annotations

import uuid
from collections.abc import Mapping
from types import MappingProxyType
from typing import Any, Self

from pydantic import Field, ModelWrapValidatorHandler, PrivateAttr, ValidationError, model_validator

from app.research.contribution_queue import BATCH_FACTS_MAX, IDEMPOTENCY_KEY_PATTERN, BatchItem
from app.research.crafts import SLUG_MAX_CHARS
from app.research.knowledge_writes import (
    PROPOSAL_FIELDS_MAX,
    PROPOSAL_SOURCES_MAX,
    STATEMENT_MAX_CHARS,
    FactProposal,
    ProposedSource,
)
from app.research.open_work import TASK_KEY_MAX_CHARS
from app.research.vocabulary import Discipline

from .mcp_argument_names import OLD_ARGUMENT_NAMES, RenamedArguments, problems
from .mcp_tool_base import Arguments

__all__ = ["FactFields", "GetProposal", "ProposeFacts"]

ONE_SUBJECT = "name a craft_slug or a category_slug, one of them"
FACT_NAMES: Mapping[str, str] = MappingProxyType({**OLD_ARGUMENT_NAMES, "idempotencyKey": "idempotency_key"})


class FactFields(RenamedArguments):
    OLD_NAMES = FACT_NAMES

    craft_slug: str | None = Field(
        default=None,
        min_length=1,
        max_length=SLUG_MAX_CHARS,
        description="The craft's slug, from find_crafts",
    )
    category_slug: str | None = Field(
        default=None,
        min_length=1,
        max_length=SLUG_MAX_CHARS,
        description="A category's slug, for a category fact",
    )
    field: Discipline = Field(description="One of the sixteen fields: the field the fact is filed under")
    fields: list[Discipline] = Field(
        default_factory=list, max_length=PROPOSAL_FIELDS_MAX, description="Up to three secondary fields"
    )
    statement: str = Field(
        min_length=1,
        max_length=STATEMENT_MAX_CHARS,
        description="One sentence stating one fact (20 characters or more)",
    )
    sources: list[ProposedSource] = Field(
        min_length=1,
        max_length=PROPOSAL_SOURCES_MAX,
        description="1 to 5 sources, each {url (https), title, licence, quotes [{text (verbatim), locator}]}",
    )
    task_key: str | None = Field(
        default=None,
        min_length=1,
        max_length=TASK_KEY_MAX_CHARS,
        description="The field or corroboration task you claimed for this fact, from list_open_work",
    )
    idempotency_key: str | None = Field(
        default=None,
        pattern=IDEMPOTENCY_KEY_PATTERN,
        description=(
            "Your key for this fact, 8 to 120 letters, digits, dots, dashes, underscores or colons: a call sent "
            "again with the same key returns the first call's proposal and never adds the fact twice; without "
            "one, the fact's own content is its key"
        ),
    )
    _fact: FactProposal | None = PrivateAttr(default=None)

    @model_validator(mode="after")
    def _a_whole_fact(self) -> Self:
        if (self.craft_slug is None) == (self.category_slug is None):
            raise ValueError(ONE_SUBJECT)
        kind, slug = ("craft", self.craft_slug) if self.craft_slug else ("category", self.category_slug)
        body = {
            "subject": {"kind": kind, "slug": slug},
            "field": self.field,
            "fields": self.fields,
            "statement": self.statement,
            "sources": self.sources,
            "task_key": self.task_key,
        }
        try:
            self._fact = FactProposal.model_validate(body)
        except ValidationError as refused:
            raise ValueError(problems(refused)) from None
        return self

    def fact(self) -> FactProposal:
        if self._fact is None:
            raise ValueError("the fact was not validated")
        return self._fact


class ProposeFacts(Arguments):
    facts: list[FactFields] = Field(
        min_length=1,
        max_length=BATCH_FACTS_MAX,
        description=(
            "1 to 25 facts, each with its subject, field, statement, sources and its own idempotency_key; each is checked "
            "on its own, so a malformed one is refused and the rest go on"
        ),
    )
    _indices: tuple[int, ...] = PrivateAttr(default=())
    _refused: tuple[BatchItem, ...] = PrivateAttr(default=())

    @model_validator(mode="wrap")
    @classmethod
    def _each_fact_on_its_own(cls, data: Any, handler: ModelWrapValidatorHandler[Self]) -> Self:
        raw = data.get("facts") if isinstance(data, Mapping) else None
        if not isinstance(raw, list) or not raw or len(raw) > BATCH_FACTS_MAX:
            return handler(data)
        kept: list[FactFields] = []
        indices: list[int] = []
        refused: list[BatchItem] = []
        for index, item in enumerate(raw):
            try:
                kept.append(FactFields.model_validate(item))
                indices.append(index)
            except ValidationError as problem:
                refused.append(
                    BatchItem(
                        index=index, accepted=False, idempotency_key=_key(item), problem=problems(problem)
                    )
                )
        model = handler({**data, "facts": kept}) if kept else cls.model_construct(facts=[])
        model._indices, model._refused = tuple(indices), tuple(refused)
        return model

    def indexed(self) -> list[tuple[int, FactFields]]:
        return list(zip(self._indices, self.facts, strict=True))

    def refused(self) -> list[BatchItem]:
        return list(self._refused)

    def notices(self) -> list[str]:
        return list(dict.fromkeys(notice for fact in self.facts for notice in fact.notices()))


class GetProposal(Arguments):
    proposal_id: uuid.UUID = Field(description="A proposal id from propose_facts, propose_page or my_work")


def _key(item: Any) -> str | None:
    if not isinstance(item, Mapping):
        return None
    key = item.get("idempotency_key", item.get("idempotencyKey"))
    return key if isinstance(key, str) and key else None
