from __future__ import annotations

import uuid
from typing import Literal, Self

from pydantic import Field, model_validator

from .base import ContractModel
from .evidence import canonical_url
from .knowledge_writes import PROPOSAL_SOURCES_MAX, GateReport, ProposedSource
from .open_work import TASK_KEY_MAX_CHARS, parse_task_key

__all__ = [
    "ADDED",
    "REFUSED",
    "SOURCE_OUTCOMES",
    "SOURCE_PROPOSALS_SCHEMA_VERSION",
    "SOURCE_TASK_KINDS",
    "SourceProposal",
    "SourceProposalReply",
    "source_task_problem",
]

SOURCE_PROPOSALS_SCHEMA_VERSION = 1
SOURCE_TASK_KINDS = (
    "RESOURCE_FACT",
    "CORROBORATE_FACT",
    "FIND_ANOTHER_SOURCE",
    "SECOND_SOURCE",
    "DEAD_SOURCE",
)
ADDED = "ADDED"
REFUSED = "REFUSED"
SOURCE_OUTCOMES = (ADDED, REFUSED)

SourceOutcome = Literal[*SOURCE_OUTCOMES]


class SourceProposal(ContractModel):
    schema_version: Literal[1] = SOURCE_PROPOSALS_SCHEMA_VERSION
    claim_id: uuid.UUID
    sources: list[ProposedSource] = Field(min_length=1, max_length=PROPOSAL_SOURCES_MAX)
    task_key: str | None = Field(default=None, min_length=1, max_length=TASK_KEY_MAX_CHARS)

    @model_validator(mode="after")
    def _each_source_once(self) -> Self:
        urls = [canonical_url(source.url) for source in self.sources]
        if len(set(urls)) != len(urls):
            raise ValueError("each source is named once; give all its quotes under it")
        return self

    @model_validator(mode="after")
    def _task_is_a_source_task(self) -> Self:
        if self.task_key is not None:
            problem = source_task_problem(self.task_key)
            if problem is not None:
                raise ValueError(problem)
        return self


class SourceProposalReply(ContractModel):
    schema_version: Literal[1] = SOURCE_PROPOSALS_SCHEMA_VERSION
    outcome: SourceOutcome
    claim_id: uuid.UUID
    quotes_added: int = Field(ge=0)
    held: bool
    gates: list[GateReport]
    message: str


def source_task_problem(key: str) -> str | None:
    task = parse_task_key(key)
    if task.kind not in SOURCE_TASK_KINDS:
        return f"{key} is not a task a source completes; a source completes a {', '.join(SOURCE_TASK_KINDS)} task"
    return None
