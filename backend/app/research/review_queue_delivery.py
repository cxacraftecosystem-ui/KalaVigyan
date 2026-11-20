from __future__ import annotations

import uuid

from pydantic import Field

from .base import ContractModel
from .monograph_document import MonographDocument
from .review_queue_parts import FactSource
from .vocabulary import EvidenceLevel

__all__ = ["DeliveredFact", "DeliveredReview", "DeliveredUnitReview", "PlacedDelivery"]


class DeliveredUnitReview(ContractModel):
    unit: str
    text: str
    claim_ids: list[uuid.UUID] = Field(default_factory=list)


class DeliveredFact(ContractModel):
    id: uuid.UUID
    text: str
    level: EvidenceLevel | None
    shown: bool
    sources: list[FactSource] = Field(default_factory=list)


class DeliveredReview(ContractModel):
    drawing: MonographDocument | None
    units: list[DeliveredUnitReview]
    facts: list[DeliveredFact]


class PlacedDelivery(ContractModel):
    label: str
    title: str
    kind: str
    delivery: DeliveredReview
