from __future__ import annotations

import logging
import uuid
from collections.abc import Collection, Iterable, Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Source
from app.research.component_specs_general_delivery import (
    DeliveredComponent,
    delivered_claim_ids,
    delivered_of,
    fresh_unit_ids,
    renamed_spec,
)

from . import knowledge_view
from .knowledge_view import ClaimView
from .monograph_generated_units import DraftUnit

__all__ = ["UNIT_TAG", "DrawnDelivery", "drawn_delivery", "stored_delivery", "with_delivered_claims"]

logger = logging.getLogger(__name__)

UNIT_TAG = "span"


class Delivering(Protocol):
    @property
    def delivered(self) -> DeliveredComponent | None: ...


@dataclass(frozen=True)
class DrawnDelivery:
    spec: dict[str, Any]
    drafts: dict[str, DraftUnit]


def stored_delivery(label: str, payload: Mapping[str, Any]) -> DeliveredComponent | None:
    try:
        return delivered_of(payload)
    except ValidationError:
        logger.warning("the stored delivery of %s is off its contract, so it is not drawn", label)
        return None


def drawn_delivery(
    delivered: DeliveredComponent,
    *,
    place: tuple[str, str],
    visible: Mapping[uuid.UUID, Any],
    taken: Collection[str],
) -> DrawnDelivery | None:
    chapter, field = place
    if any(claim not in visible for claim in delivered_claim_ids(delivered.units)):
        return None
    refs = sorted(delivered.units)
    names = dict(zip(refs, fresh_unit_ids(len(refs), taken), strict=True))
    drafts = {
        names[ref]: DraftUnit(
            names[ref],
            chapter,
            field,
            delivered.units[ref].text,
            tuple(delivered.units[ref].claim_ids),
            UNIT_TAG,
        )
        for ref in refs
    }
    return DrawnDelivery(spec=renamed_spec(delivered.spec, names), drafts=drafts)


async def with_delivered_claims(
    session: AsyncSession,
    components: Iterable[Delivering],
    visible: Mapping[uuid.UUID, ClaimView],
    rows: Mapping[uuid.UUID, Source],
) -> tuple[dict[uuid.UUID, ClaimView], dict[uuid.UUID, Source]]:
    wanted = [
        claim
        for component in components
        if component.delivered is not None
        for claim in delivered_claim_ids(component.delivered.units)
        if claim not in visible
    ]
    if not wanted:
        return dict(visible), dict(rows)
    more, sources = await knowledge_view.claims_by_id(session, wanted)
    return {**visible, **more}, {**rows, **sources}
