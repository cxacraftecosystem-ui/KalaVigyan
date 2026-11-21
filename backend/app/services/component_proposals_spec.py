from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import InvalidInput
from app.research.component_proposals import ComponentProposalDraft
from app.research.component_specs import checked_spec
from app.research.component_specs_general_delivery import (
    delivered_claim_ids,
    problems_sentence,
    spec_problems,
    unit_problems,
)

from . import knowledge_view
from .dataset_cells import checked_cells

__all__ = ["NO_KNOWN", "CheckedDelivery", "checked_delivery", "shown_texts"]

REFUSED = "The component cannot be drawn as delivered: {problems}."
NO_KNOWN: Mapping[uuid.UUID, Sequence[str]] = MappingProxyType({})


@dataclass(frozen=True)
class CheckedDelivery:
    spec: dict[str, Any]
    units: dict[str, Any]
    claim_ids: tuple[uuid.UUID, ...]


async def checked_delivery(
    session: AsyncSession,
    draft: ComponentProposalDraft,
    *,
    known: Mapping[uuid.UUID, Sequence[str]] = NO_KNOWN,
) -> CheckedDelivery:
    if draft.spec is None:
        raise InvalidInput("A delivered component carries its spec")
    problems = spec_problems(draft.kind, draft.spec, draft.units)
    if problems:
        raise InvalidInput(REFUSED.format(problems=problems_sentence(problems)))
    checked = checked_spec(draft.kind, draft.spec)
    cells = await checked_cells(session, checked)
    claim_ids = delivered_claim_ids(draft.units)
    shown = await shown_texts(session, [claim for claim in claim_ids if claim not in known])
    problems = [*cells.problems, *unit_problems(draft.units, {**shown, **known}, cells.rows)]
    if problems:
        raise InvalidInput(REFUSED.format(problems=problems_sentence(problems)))
    spec = checked.model_dump(mode="json")
    if cells.dataset is not None:
        spec["dataset"] = cells.dataset
    units = {ref: unit.model_dump(mode="json") for ref, unit in sorted(draft.units.items())}
    return CheckedDelivery(spec=spec, units=units, claim_ids=tuple(claim_ids))


async def shown_texts(session: AsyncSession, claim_ids: Sequence[uuid.UUID]) -> dict[uuid.UUID, list[str]]:
    visible, _ = await knowledge_view.claims_by_id(session, claim_ids)
    return {
        claim_id: [view.text, *(str(cite["quote"]) for cite in view.citations if cite.get("quote"))]
        for claim_id, view in visible.items()
    }
