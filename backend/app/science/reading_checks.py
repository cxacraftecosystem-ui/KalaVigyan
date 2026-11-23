from __future__ import annotations

from dataclasses import dataclass

from app.schemas.science import EnvelopeCheck

from .envelopes import STAGE_ENVELOPES, envelope_check
from .units import Bounds, normalised_bounds

__all__ = ["OUTSIDE", "ReadingCheck", "enveloped", "reading_check"]

OUTSIDE = "OUTSIDE"


@dataclass(frozen=True)
class ReadingCheck:
    bounds: Bounds
    envelope: EnvelopeCheck

    @property
    def outside(self) -> bool:
        return self.envelope.status == OUTSIDE


def reading_check(stage_type: str, quantity: str, stated: Bounds, unit: str) -> ReadingCheck:
    bounds = normalised_bounds(quantity, stated, unit)
    return ReadingCheck(bounds=bounds, envelope=envelope_check(stage_type, quantity, bounds.low, bounds.high))


def enveloped() -> tuple[tuple[str, str], ...]:
    return tuple(sorted(STAGE_ENVELOPES))
