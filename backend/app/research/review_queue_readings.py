from __future__ import annotations

import uuid
from collections.abc import Iterable

from .base import ContractModel
from .review_queue_parts import FactSource
from .review_switch import AGENT, CONTRIBUTION, RESEARCH

__all__ = ["CONTRIBUTED_CLAIM_ORIGIN", "ReadingReview", "reading_origin"]

CONTRIBUTED_CLAIM_ORIGIN = "CONTRIBUTION"


class ReadingReview(ContractModel):
    stated: str
    quantity: str
    unit: str
    min: float | None
    max: float | None
    envelope_min: float | None
    envelope_max: float | None
    condition: str
    stage: str
    stage_type: str
    claim_id: uuid.UUID
    statement: str
    sources: list[FactSource]


def reading_origin(claim_origin: str, found_by: Iterable[str | None]) -> str:
    if AGENT in set(found_by):
        return AGENT
    return CONTRIBUTION if claim_origin == CONTRIBUTED_CLAIM_ORIGIN else RESEARCH
