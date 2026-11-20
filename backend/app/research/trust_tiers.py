from __future__ import annotations

import hashlib
import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Literal

from pydantic import Field

from app.core.rate_limit import FACT_PROPOSALS_PER_WINDOW
from app.models.contributions import TIER_NOTE_CHARS, TRUST_TIERS

from .base import ContractModel
from .open_work import RESERVATIONS_HELD_MAX
from .review_switch import (
    APPROVAL,
    APPROVED_STATUS,
    AUTO,
    PUBLISHED,
    Placement,
    placement,
)

__all__ = [
    "DRAWN",
    "ESTABLISHED",
    "ESTABLISHED_ACCEPTED_MIN",
    "ESTABLISHED_SHARE_MIN",
    "NEW",
    "NEWCOMER",
    "PROVEN",
    "PROVEN_ACCEPTED_MIN",
    "PROVEN_SHARE_MIN",
    "REVIEW_SAMPLE_PERCENT",
    "ROLE",
    "SWITCH",
    "TIER_FACTS_PER_HOUR",
    "TIER_TASKS_HELD",
    "TRUSTED",
    "TRUST_TIERS",
    "TierOverrideView",
    "TierPlacement",
    "TierRecord",
    "TierUpdate",
    "TrustStanding",
    "TrustStandings",
    "TrustTier",
    "drawn_for_review",
    "earned_tier",
    "tier_placement",
]

TRUST_SCHEMA_VERSION = 1
NEW, ESTABLISHED, PROVEN = TRUST_TIERS
ESTABLISHED_ACCEPTED_MIN = 5
ESTABLISHED_SHARE_MIN = 0.75
PROVEN_ACCEPTED_MIN = 25
PROVEN_SHARE_MIN = 0.9
REVIEW_SAMPLE_PERCENT = 20
PERCENT = 100
SAMPLE_BYTES = 4
TIER_TASKS_HELD: Mapping[str, int] = MappingProxyType(
    {NEW: RESERVATIONS_HELD_MAX, ESTABLISHED: 10, PROVEN: 20}
)
TIER_FACTS_PER_HOUR: Mapping[str, int] = MappingProxyType(
    {NEW: FACT_PROPOSALS_PER_WINDOW, ESTABLISHED: 60, PROVEN: 150}
)
ROLE, DRAWN, TRUSTED, NEWCOMER, SWITCH = "ROLE", "DRAWN", "TRUSTED", "NEWCOMER", "SWITCH"

TrustTier = Literal[*TRUST_TIERS]


@dataclass(frozen=True)
class TierRecord:
    accepted: int = 0
    refused: int = 0
    waiting: int = 0

    @property
    def decided(self) -> int:
        return self.accepted + self.refused

    @property
    def share(self) -> float | None:
        return None if self.decided == 0 else self.accepted / self.decided


@dataclass(frozen=True)
class TierPlacement:
    placed: Placement
    why: str


def earned_tier(record: TierRecord) -> str:
    share = record.share
    if share is None:
        return NEW
    if record.accepted >= PROVEN_ACCEPTED_MIN and share >= PROVEN_SHARE_MIN:
        return PROVEN
    if record.accepted >= ESTABLISHED_ACCEPTED_MIN and share >= ESTABLISHED_SHARE_MIN:
        return ESTABLISHED
    return NEW


def drawn_for_review(token: uuid.UUID) -> bool:
    digest = hashlib.sha256(token.bytes).digest()
    return int.from_bytes(digest[:SAMPLE_BYTES], "big") % PERCENT < REVIEW_SAMPLE_PERCENT


def tier_placement(mode: str, *, proposer_reviews: bool, tier: str, drawn: bool) -> TierPlacement:
    if proposer_reviews:
        return TierPlacement(placement(mode, proposer_reviews=True), ROLE)
    if tier == PROVEN and drawn:
        return TierPlacement(placement(AUTO, proposer_reviews=False), DRAWN)
    if tier == PROVEN:
        return TierPlacement(
            Placement(PUBLISHED, APPROVED_STATUS, approved_at_once=True, queued=False), TRUSTED
        )
    if tier == NEW:
        return TierPlacement(placement(APPROVAL, proposer_reviews=False), NEWCOMER)
    return TierPlacement(placement(mode, proposer_reviews=False), SWITCH)


class TierOverrideView(ContractModel):
    tier: TrustTier
    note: str | None
    set_at: datetime
    set_by: uuid.UUID | None


class TrustStanding(ContractModel):
    schema_version: Literal[1] = TRUST_SCHEMA_VERSION
    user_id: uuid.UUID
    name: str | None = None
    role: str
    tier: TrustTier
    earned: TrustTier
    accepted: int = Field(ge=0)
    refused: int = Field(ge=0)
    waiting: int = Field(ge=0)
    tasks_held_max: int = Field(ge=1)
    facts_per_hour: int = Field(ge=1)
    review_sample_percent: int = Field(ge=0, le=PERCENT)
    override: TierOverrideView | None = None


class TrustStandings(ContractModel):
    schema_version: Literal[1] = TRUST_SCHEMA_VERSION
    accounts: list[TrustStanding]


class TierUpdate(ContractModel):
    tier: TrustTier | None = Field(
        description="The tier this account is held at whatever its record; null gives it back to its record"
    )
    note: str | None = Field(default=None, min_length=1, max_length=TIER_NOTE_CHARS)
