from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from app.schemas.science import EnvelopeCheck, envelope_status

__all__ = [
    "PHYSICAL_CONSTANTS",
    "STAGE_ENVELOPES",
    "PhysicalConstant",
    "StageEnvelope",
    "envelope_check",
    "envelope_for",
]


@dataclass(frozen=True)
class PhysicalConstant:
    key: str
    label: str
    quantity: str
    min: float
    max: float
    claim_key: str


@dataclass(frozen=True)
class StageEnvelope:
    stage_type: str
    quantity: str
    min: float
    max: float
    basis: tuple[str, ...]


PHYSICAL_CONSTANTS: Mapping[str, PhysicalConstant] = MappingProxyType(
    {
        constant.key: constant
        for constant in (
            PhysicalConstant(
                "water-boiling-point",
                "Water boils at 1 atm",
                "TEMPERATURE",
                100.0,
                100.0,
                "sci-constant-water-boiling-point",
            ),
            PhysicalConstant(
                "quartz-inversion",
                "Quartz α to β inversion",
                "TEMPERATURE",
                573.0,
                573.0,
                "sci-constant-quartz-inversion",
            ),
            PhysicalConstant(
                "kaolinite-dehydroxylation",
                "Kaolinite dehydroxylation commonly occurs",
                "TEMPERATURE",
                400.0,
                700.0,
                "sci-constant-kaolinite-dehydroxylation-range",
            ),
            PhysicalConstant(
                "beeswax-melting-range",
                "Beeswax melts",
                "TEMPERATURE",
                62.0,
                64.0,
                "sci-constant-beeswax-melting-range",
            ),
            PhysicalConstant(
                "brass-melting-range",
                "Brass melts",
                "TEMPERATURE",
                900.0,
                940.0,
                "sci-constant-brass-melting-range",
            ),
        )
    }
)

STAGE_ENVELOPES: Mapping[tuple[str, str], StageEnvelope] = MappingProxyType(
    {
        (envelope.stage_type, envelope.quantity): envelope
        for envelope in (
            StageEnvelope("DYE", "TEMPERATURE", 20.0, 100.0, ("water-boiling-point",)),
            StageEnvelope("DYE", "PH", 2.0, 12.0, ()),
            StageEnvelope("MORDANT", "TEMPERATURE", 15.0, 100.0, ("water-boiling-point",)),
            StageEnvelope(
                "FIRE", "TEMPERATURE", 500.0, 1300.0, ("kaolinite-dehydroxylation", "quartz-inversion")
            ),
            StageEnvelope("CAST", "TEMPERATURE", 700.0, 1200.0, ("brass-melting-range",)),
        )
    }
)


def envelope_for(stage_type: str, quantity: str) -> StageEnvelope | None:
    return STAGE_ENVELOPES.get((stage_type, quantity))


def envelope_check(stage_type: str, quantity: str, low: float | None, high: float | None) -> EnvelopeCheck:
    envelope = envelope_for(stage_type, quantity)
    if envelope is None:
        return EnvelopeCheck(status="NONE", min=None, max=None)
    status = envelope_status(low, high, envelope.min, envelope.max)
    return EnvelopeCheck(status=status, min=envelope.min, max=envelope.max)
