from __future__ import annotations

import uuid

from .base import ContractModel

__all__ = ["FactSource", "GateCheck", "RelatedFact", "SourceQuote"]


class SourceQuote(ContractModel):
    text: str
    locator: str | None


class FactSource(ContractModel):
    title: str
    url: str | None
    licence: str | None
    reliability: str
    quotes: list[SourceQuote]


class RelatedFact(ContractModel):
    id: uuid.UUID
    text: str


class GateCheck(ContractModel):
    gate: str
    passed: bool
    reasons: list[str]
    model: str | None
    related: list[RelatedFact]
