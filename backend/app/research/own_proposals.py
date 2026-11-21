from __future__ import annotations

import uuid
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime
from types import MappingProxyType
from typing import Literal

from pydantic import Field

from app.models.component_kinds import PIECE_KINDS
from app.models.enums import PIECE_SUBJECT_KINDS

from .base import ContractModel
from .component_proposals import ComponentProposalDraft
from .component_specs import not_contributable
from .crafts import QUESTION_MAX_CHARS, SLUG_MAX_CHARS
from .knowledge_api import FieldInfo
from .knowledge_writes import GateReport
from .open_work import COMPONENT_NEEDS
from .vocabulary import Discipline, PieceKind, PieceSubjectKind

__all__ = [
    "COMPONENT",
    "COMPONENT_STATES",
    "CONTRIBUTION_TERMS_VERSION",
    "FACT",
    "FACT_STATES",
    "OWN_PROPOSALS_MAX",
    "OWN_PROPOSALS_SCHEMA_VERSION",
    "PROPOSAL_STATES",
    "WAITING",
    "ComponentProposalBody",
    "LibrarySearch",
    "OwnProposal",
    "OwnProposals",
    "ProposalForm",
    "TermsAcceptance",
    "TermsStatus",
    "component_reasons",
    "component_state",
    "fact_reasons",
    "fact_state",
    "newest_first",
    "withdraw_refusal",
]

OWN_PROPOSALS_SCHEMA_VERSION = 1
CONTRIBUTION_TERMS_VERSION = "2026-11-19"
CONTRIBUTION_TERMS_VERSIONS = (CONTRIBUTION_TERMS_VERSION,)
OWN_PROPOSALS_MAX = 100
PROPOSAL_KINDS = ("FACT", "COMPONENT")
FACT, COMPONENT = PROPOSAL_KINDS
PROPOSAL_STATES = ("PUBLISHED", "APPROVED", "WAITING", "REFUSED", "REJECTED", "WITHDRAWN", "RETIRED")
PUBLISHED, APPROVED, WAITING, REFUSED, REJECTED, WITHDRAWN, RETIRED = PROPOSAL_STATES
STAYS_PUBLISHED = "It is published, and a published contribution stays published: consent cannot be revoked."
STAYS_APPROVED = "It is approved, and an approved contribution stays: consent cannot be revoked."
NO_LONGER_WAITING = "It no longer waits for review, so there is nothing to withdraw."

FACT_STATES: Mapping[str, str] = MappingProxyType(
    {
        "DRAFT": WAITING,
        "PROPOSED": PUBLISHED,
        "IN_REVIEW": PUBLISHED,
        "APPROVED": PUBLISHED,
        "REJECTED": REJECTED,
        "WITHDRAWN": WITHDRAWN,
        "RETRACTED": RETIRED,
        "SUPERSEDED": RETIRED,
    }
)
COMPONENT_STATES: Mapping[str, str] = MappingProxyType(
    {"PENDING": WAITING, "APPROVED": APPROVED, "REJECTED": REJECTED, "WITHDRAWN": WITHDRAWN}
)

ProposalKind = Literal[*PROPOSAL_KINDS]
ProposalState = Literal[*PROPOSAL_STATES]
TermsVersion = Literal[*CONTRIBUTION_TERMS_VERSIONS]


class OwnProposal(ContractModel):
    id: uuid.UUID
    kind: ProposalKind
    state: ProposalState
    status: str
    text: str
    description: str | None = None
    label: str | None = None
    component_kind: PieceKind | None = None
    field: Discipline | None
    subject_name: str | None
    craft_slug: str | None
    created_at: datetime
    reasons: list[str] = Field(default_factory=list)
    gates: list[GateReport] = Field(default_factory=list)


class OwnProposals(ContractModel):
    schema_version: Literal[1] = OWN_PROPOSALS_SCHEMA_VERSION
    items: list[OwnProposal]


class TermsStatus(ContractModel):
    version: str
    accepted_at: datetime | None


class TermsAcceptance(ContractModel):
    version: TermsVersion


class ProposalForm(ContractModel):
    schema_version: Literal[1] = OWN_PROPOSALS_SCHEMA_VERSION
    terms: TermsStatus
    fields: list[FieldInfo]
    kinds: list[PieceKind] = Field(
        default_factory=lambda: [kind for kind in PIECE_KINDS if not_contributable(kind) is None]
    )
    subject_kinds: list[PieceSubjectKind] = Field(default_factory=lambda: list(PIECE_SUBJECT_KINDS))
    needs: dict[str, list[PieceKind]] = Field(
        default_factory=lambda: {need: list(kinds) for need, kinds in COMPONENT_NEEDS.items()}
    )


class LibrarySearch(ContractModel):
    query: str | None = Field(default=None, min_length=1, max_length=QUESTION_MAX_CHARS)
    craft_slug: str | None = Field(default=None, min_length=1, max_length=SLUG_MAX_CHARS)
    field: Discipline | None = None
    kind: PieceKind | None = None


class ComponentProposalBody(ContractModel, ComponentProposalDraft):
    pass


def fact_state(status: str, gates: Sequence[GateReport]) -> str:
    state = _state(FACT_STATES, status, "claim")
    if state == REJECTED and any(not gate.passed for gate in gates):
        return REFUSED
    return state


def component_state(status: str) -> str:
    return _state(COMPONENT_STATES, status, "component proposal")


def fact_reasons(state: str, gates: Sequence[GateReport], reviewer_note: str | None) -> list[str]:
    if state == REFUSED:
        refused = next(gate for gate in gates if not gate.passed)
        return list(refused.reasons)
    return _reviewer_reasons(state, reviewer_note)


def component_reasons(state: str, review_note: str | None) -> list[str]:
    return _reviewer_reasons(state, review_note)


def withdraw_refusal(state: str) -> str | None:
    if state == WAITING:
        return None
    if state == PUBLISHED:
        return STAYS_PUBLISHED
    if state == APPROVED:
        return STAYS_APPROVED
    return NO_LONGER_WAITING


def newest_first(items: Iterable[OwnProposal], limit: int = OWN_PROPOSALS_MAX) -> list[OwnProposal]:
    ordered = sorted(items, key=lambda item: (item.created_at, str(item.id)), reverse=True)
    return ordered[:limit]


def _state(states: Mapping[str, str], status: str, what: str) -> str:
    state = states.get(status)
    if state is None:
        raise ValueError(f"a {what} status {status!r} has no contributor state")
    return state


def _reviewer_reasons(state: str, note: str | None) -> list[str]:
    if state == REJECTED and note and note.strip():
        return [note.strip()]
    return []
