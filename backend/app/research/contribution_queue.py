from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timedelta
from typing import Literal

from pydantic import Field

from app.models.contributions import IDEMPOTENCY_KEY_CHARS, QUEUE_STATES

from .base import ContractModel
from .knowledge_writes import FactProposal, ProposalReply, ProposalSubject
from .review_switch import ProposalOutcome
from .vocabulary import Discipline

__all__ = [
    "ATTEMPTS_MAX",
    "BATCH_FACTS_MAX",
    "CHECKING",
    "DONE",
    "FAILED",
    "IDEMPOTENCY_KEY_PATTERN",
    "LEASE_TIME",
    "QUEUED",
    "QUEUE_SCHEMA_VERSION",
    "QUEUE_STATES",
    "RECENT_PROPOSALS_MAX",
    "STREAM_REQUEST_PREFIX",
    "BatchItem",
    "FactBatchBody",
    "ProposalBatch",
    "ProposalTicket",
    "ProposalTickets",
    "QueueState",
    "QueuedFactBody",
    "content_key",
    "proposal_fingerprint",
    "retry_delay",
    "stream_request_id",
    "subject_key",
]

QUEUE_SCHEMA_VERSION = 1
QUEUED, CHECKING, DONE, FAILED = QUEUE_STATES
BATCH_FACTS_MAX = 25
ATTEMPTS_MAX = 5
RETRY_FIRST = timedelta(seconds=30)
RETRY_LONGEST = timedelta(minutes=30)
LEASE_TIME = timedelta(minutes=15)
RECENT_PROPOSALS_MAX = 50
IDEMPOTENCY_KEY_PATTERN = r"^[A-Za-z0-9._:-]{8,120}$"
CONTENT_KEY_PREFIX = "fact:"
CONTENT_KEY_DIGITS = 40
STREAM_REQUEST_PREFIX = "contribution-"

QueueState = Literal[*QUEUE_STATES]


class ProposalTicket(ContractModel):
    schema_version: Literal[1] = QUEUE_SCHEMA_VERSION
    proposal_id: uuid.UUID
    kind: Literal["FACT"] = "FACT"
    state: QueueState
    idempotency_key: str = Field(min_length=1, max_length=IDEMPOTENCY_KEY_CHARS)
    replayed: bool = False
    subject: ProposalSubject
    field: Discipline
    statement: str
    task_key: str | None = None
    position: int | None = Field(default=None, ge=0)
    attempts: int = Field(ge=0)
    queued_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    next_try_at: datetime | None = None
    outcome: ProposalOutcome | None = None
    reply: ProposalReply | None = None
    model_calls: int = Field(default=0, ge=0)
    cost_usd: float = Field(default=0.0, ge=0.0)
    message: str
    notices: list[str] = Field(default_factory=list)


class ProposalTickets(ContractModel):
    schema_version: Literal[1] = QUEUE_SCHEMA_VERSION
    proposals: list[ProposalTicket]


class BatchItem(ContractModel):
    index: int = Field(ge=0)
    accepted: bool
    idempotency_key: str | None = None
    ticket: ProposalTicket | None = None
    problem: str | None = None


class ProposalBatch(ContractModel):
    schema_version: Literal[1] = QUEUE_SCHEMA_VERSION
    accepted: int = Field(ge=0)
    refused: int = Field(ge=0)
    items: list[BatchItem]
    message: str
    notices: list[str] = Field(default_factory=list)


class QueuedFactBody(ContractModel):
    idempotency_key: str | None = Field(default=None, pattern=IDEMPOTENCY_KEY_PATTERN)
    proposal: FactProposal


class FactBatchBody(ContractModel):
    facts: list[QueuedFactBody] = Field(min_length=1, max_length=BATCH_FACTS_MAX)


def proposal_fingerprint(proposal: FactProposal) -> str:
    body = proposal.model_dump(mode="json", by_alias=True)
    canonical = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def content_key(fingerprint: str) -> str:
    return f"{CONTENT_KEY_PREFIX}{fingerprint[:CONTENT_KEY_DIGITS]}"


def subject_key(subject: ProposalSubject) -> str:
    return f"{subject.kind}:{subject.slug.casefold()}"


def retry_delay(attempts: int) -> timedelta:
    doubled = RETRY_FIRST * 2 ** max(0, attempts - 1)
    return min(doubled, RETRY_LONGEST)


def stream_request_id(proposal_id: uuid.UUID) -> str:
    return f"{STREAM_REQUEST_PREFIX}{proposal_id.hex}"
