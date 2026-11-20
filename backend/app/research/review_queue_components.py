from __future__ import annotations

from collections.abc import Iterable

from pydantic import Field

from .base import ContractModel
from .component_proposals import (
    ComponentProposalDraft,
    ProposedSubject,
    content_words,
    match_reasons,
    word_overlap,
)
from .knowledge_api import ComponentSummary
from .review_queue_delivery import DeliveredReview
from .vocabulary import Discipline

__all__ = ["CLOSEST_SHOWN", "ClosestComponent", "ComponentReview", "closest_components"]

CLOSEST_SHOWN = 3
OVERLAP_DIGITS = 3


class ClosestComponent(ContractModel):
    component: ComponentSummary
    overlap: float = Field(ge=0.0, le=1.0)
    reasons: list[str]


def closest_components(
    draft: ComponentProposalDraft, candidates: Iterable[ComponentSummary], *, limit: int = CLOSEST_SHOWN
) -> list[ClosestComponent]:
    proposed = content_words(f"{draft.title} {draft.description}")
    seen: set[str] = set()
    ranked: list[ClosestComponent] = []
    for candidate in candidates:
        if candidate.label in seen or candidate.label == draft.extends:
            continue
        seen.add(candidate.label)
        overlap = word_overlap(proposed, content_words(f"{candidate.title} {candidate.description}"))
        reasons = match_reasons(draft, candidate)
        ranked.append(
            ClosestComponent(component=candidate, overlap=round(overlap, OVERLAP_DIGITS), reasons=reasons)
        )
    return sorted(ranked, key=lambda found: (-len(found.reasons), -found.overlap, found.component.label))[
        :limit
    ]


class ComponentReview(ContractModel):
    label: str
    title: str
    description: str
    kind: str
    field: Discipline
    fields: list[Discipline]
    subjects: list[ProposedSubject]
    considered_labels: list[str]
    extends: str | None
    extension: str | None
    task_key: str | None
    closest: list[ClosestComponent]
    delivery: DeliveredReview | None = None
