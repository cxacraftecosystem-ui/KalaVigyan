from __future__ import annotations

from .base import ContractModel
from .review_queue_parts import FactSource, RelatedFact
from .structure_proposals import StructureCheck, StructureItem, StructureKind, StructureSubject
from .vocabulary import Discipline

__all__ = ["StructureReview"]


class StructureReview(ContractModel):
    kind: StructureKind
    subject: StructureSubject
    subject_name: str
    page_url: str
    target: str | None
    current: str | None
    item: StructureItem
    statement: str | None
    field: Discipline | None
    note: str | None
    task_key: str | None
    sources: list[FactSource]
    checks: list[StructureCheck]
    conflicting: list[RelatedFact]
    stale: str | None
